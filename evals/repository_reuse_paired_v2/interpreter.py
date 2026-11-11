"""Pure, deliberately small interpreter. Candidate source is never exec'd/imported."""
from __future__ import annotations
import ast
import math
from dataclasses import dataclass

class Unsupported(ValueError):
    pass

@dataclass(frozen=True)
class Reference:
    name: str

class Returned(Exception):
    def __init__(self,value): self.value=value

class Program:
    def __init__(self,raw,*,function,argument,helper):
        if len(raw)>8192: raise Unsupported('source_bytes')
        self.tree=ast.parse(raw)
        nodes=list(ast.walk(self.tree))
        if len(nodes)>2048: raise Unsupported('ast_nodes')
        allowed=(ast.Module,ast.ImportFrom,ast.alias,ast.FunctionDef,ast.arguments,ast.arg,
            ast.Assign,ast.AugAssign,ast.For,ast.If,ast.Return,ast.Expr,ast.Call,
            ast.Attribute,ast.Name,ast.Load,ast.Store,ast.Constant,ast.List,ast.Tuple,
            ast.Dict,ast.Set,ast.Subscript,ast.Slice,ast.BinOp,ast.UnaryOp,ast.Compare,
            ast.BoolOp,ast.Add,ast.Sub,ast.Mult,ast.FloorDiv,ast.Div,ast.USub,ast.Not,
            ast.Eq,ast.NotEq,ast.Is,ast.IsNot,ast.In,ast.NotIn,ast.Lt,ast.LtE,ast.Gt,ast.GtE,
            ast.And,ast.Or)
        if any(not isinstance(n,allowed) for n in nodes): raise Unsupported('syntax_subset')
        self.env={};self.helper=helper
        functions=[]
        for node in self.tree.body:
            if isinstance(node,ast.ImportFrom):
                if node.level or len(node.names)!=1 or node.names[0].name=='*': raise Unsupported('import')
                imported=node.module+'.'+node.names[0].name
                if imported not in (helper,helper.rsplit('.',1)[0]): raise Unsupported('import')
                self.env[node.names[0].asname or node.names[0].name]=Reference(imported)
            elif isinstance(node,ast.FunctionDef): functions.append(node)
            else: raise Unsupported('module_effect')
        if len(functions)!=1: raise Unsupported('function_count')
        self.function=functions[0];args=self.function.args
        if self.function.name!=function or self.function.decorator_list or self.function.type_comment or self.function.returns is not None or any(a.annotation is not None for a in args.args) or getattr(self.function,'type_params',[]): raise Unsupported('function_shape')
        if [a.arg for a in args.args]!=[argument] or args.posonlyargs or args.kwonlyargs or args.defaults or args.kw_defaults or args.vararg or args.kwarg: raise Unsupported('signature')
        self.argument=argument
        # A local assignment makes Python treat the name as local throughout
        # the function, even before the assignment has executed.
        self.set_shadowed=any(isinstance(n,ast.Name) and n.id=='set' and isinstance(n.ctx,ast.Store)
                              for n in ast.walk(self.function))
        for node in nodes:
            if isinstance(node,ast.Name) and node.id.startswith('_'): raise Unsupported('private_name')
            if isinstance(node,ast.Attribute) and node.attr.startswith('_'): raise Unsupported('private_attribute')
            if isinstance(node,ast.Constant): self.bound(node.value)
        self.steps=0

    def tick(self):
        self.steps+=1
        if self.steps>4096: raise Unsupported('step_budget')

    def bound(self,value,depth=0):
        if depth>12: raise Unsupported('value_depth')
        if value is None or type(value) is bool: return value
        if type(value) in (int,float):
            if not math.isfinite(value) or abs(value)>10**12: raise Unsupported('numeric_bound')
        elif isinstance(value,Reference): return value
        elif type(value) is str:
            if len(value)>4096: raise Unsupported('string_bound')
        elif type(value) in (list,tuple,set,dict):
            if len(value)>128: raise Unsupported('collection_bound')
            for item in value: self.bound(item,depth+1)
            if isinstance(value,dict):
                for item in value.values(): self.bound(item,depth+1)
        else: raise Unsupported('value_type')
        return value

    def run(self,value,helper):
        from copy import deepcopy
        self.steps=0;self.callback=helper
        held_input=self.bound(deepcopy(value))
        original_input=deepcopy(held_input)
        env={**self.env,self.argument:held_input}
        try: self.statements(self.function.body,env)
        except Returned as result: output=result.value
        else: output=None
        if held_input != original_input: raise Unsupported('input_mutated')
        return self.bound(output)

    def assign(self,node,value,env):
        self.bound(value)
        if isinstance(node,ast.Name): env[node.id]=value
        elif isinstance(node,(ast.Tuple,ast.List)) and isinstance(value,(tuple,list)) and len(node.elts)==len(value):
            for target,item in zip(node.elts,value): self.assign(target,item,env)
        elif isinstance(node,ast.Subscript):
            target=self.expr(node.value,env);key=self.expr(node.slice,env)
            if type(target) not in (dict,list): raise Unsupported('assignment_target')
            if type(target) is dict and key not in target and len(target)>=128: raise Unsupported('collection_bound')
            target[key]=value
        else: raise Unsupported('assignment')

    def statements(self,nodes,env):
        for node in nodes:
            self.tick()
            if isinstance(node,ast.Assign):
                if len(node.targets)!=1: raise Unsupported('multiple_assign')
                self.assign(node.targets[0],self.expr(node.value,env),env)
            elif isinstance(node,ast.AugAssign):
                value=self.binary(node.op,self.expr(node.target,env),self.expr(node.value,env));self.assign(node.target,value,env)
            elif isinstance(node,ast.For):
                from copy import deepcopy
                if node.orelse: raise Unsupported('loop_else')
                values=self.expr(node.iter,env)
                if type(values) not in (list,tuple,dict,set): raise Unsupported('iteration')
                before=deepcopy(self.bound(values))
                for value in list(self.bound(values)):
                    self.tick();self.assign(node.target,value,env);self.statements(node.body,env)
                    if values != before: raise Unsupported('iteration_mutated')
            elif isinstance(node,ast.If): self.statements(node.body if self.expr(node.test,env) else node.orelse,env)
            elif isinstance(node,ast.Return): raise Returned(self.expr(node.value,env))
            elif isinstance(node,ast.Expr): self.expr(node.value,env)
            else: raise Unsupported('statement')

    def binary(self,op,left,right):
        if type(op) is ast.Add:
            if type(left) in (list,tuple,str):
                if type(right) is not type(left) or len(left)+len(right)>128: raise Unsupported('concatenation')
            result=left+right
        elif type(op) in (ast.Sub,ast.Mult,ast.Div,ast.FloorDiv):
            if type(left) not in (int,float) or type(right) not in (int,float): raise Unsupported('numeric_operator')
            result={ast.Sub:lambda:left-right,ast.Mult:lambda:left*right,ast.Div:lambda:left/right,ast.FloorDiv:lambda:left//right}[type(op)]()
        else: raise Unsupported('operator')
        return self.bound(result)

    def expr(self,node,env,depth=0):
        self.tick()
        if depth>40: raise Unsupported('expression_depth')
        get=lambda child:self.expr(child,env,depth+1)
        if node is None:return None
        if isinstance(node,ast.Constant):return self.bound(node.value)
        if isinstance(node,ast.Name):
            if node.id not in env: raise Unsupported('unbound_name')
            return env[node.id]
        if isinstance(node,(ast.List,ast.Tuple,ast.Set)):
            cls={ast.List:list,ast.Tuple:tuple,ast.Set:set}[type(node)];return self.bound(cls(get(x) for x in node.elts))
        if isinstance(node,ast.Dict):
            if any(k is None for k in node.keys): raise Unsupported('mapping_unpack')
            return self.bound({get(k):get(v) for k,v in zip(node.keys,node.values)})
        if isinstance(node,ast.BinOp): return self.binary(node.op,get(node.left),get(node.right))
        if isinstance(node,ast.UnaryOp):
            value=get(node.operand)
            if isinstance(node.op,ast.Not):return not value
            if isinstance(node.op,ast.USub) and type(value) in (int,float):return self.bound(-value)
            raise Unsupported('unary')
        if isinstance(node,ast.BoolOp):
            value=get(node.values[0])
            for child in node.values[1:]:
                if (isinstance(node.op,ast.And) and not value) or (isinstance(node.op,ast.Or) and value): break
                value=get(child)
            return value
        if isinstance(node,ast.Compare):
            left=get(node.left)
            for op,child in zip(node.ops,node.comparators):
                right=get(child)
                predicates={ast.Eq:lambda:left==right,ast.NotEq:lambda:left!=right,ast.Is:lambda:left is right,ast.IsNot:lambda:left is not right,ast.In:lambda:left in right,ast.NotIn:lambda:left not in right,ast.Lt:lambda:left<right,ast.LtE:lambda:left<=right,ast.Gt:lambda:left>right,ast.GtE:lambda:left>=right}
                if type(op) not in predicates or not predicates[type(op)]():return False
                left=right
            return True
        if isinstance(node,ast.Subscript):
            target=get(node.value)
            if type(target) not in (str,list,tuple,dict):raise Unsupported('subscript')
            if isinstance(node.slice,ast.Slice):
                key=slice(get(node.slice.lower),get(node.slice.upper),get(node.slice.step))
            else:key=get(node.slice)
            return self.bound(target[key])
        if isinstance(node,ast.Call):
            if node.keywords or len(node.args)>3:raise Unsupported('call_arguments')
            args=[get(a) for a in node.args]
            if isinstance(node.func,ast.Name) and node.func.id=='set':
                if self.set_shadowed:raise Unsupported('shadowed_set')
                if 'set' not in env:
                    if args:raise Unsupported('set_arguments')
                    return self.bound(set())
            if isinstance(node.func,ast.Name):ref=get(node.func)
            elif isinstance(node.func,ast.Attribute):
                obj=get(node.func.value);name=node.func.attr
                if isinstance(obj,Reference):ref=Reference(obj.name+'.'+name)
                else:
                    methods={list:{'append'},dict:{'get'},set:{'add'},str:{'casefold','upper','lower','strip','split','join'}}
                    if name not in methods.get(type(obj),set()):raise Unsupported('method')
                    if name in ('append','add') and len(obj)>=128:raise Unsupported('collection_bound')
                    return self.bound(getattr(obj,name)(*args))
            else:raise Unsupported('call')
            if not isinstance(ref,Reference) or ref.name!=self.helper:raise Unsupported('call_target')
            return self.bound(self.callback(*args))
        raise Unsupported('expression')
