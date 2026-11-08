-- Opt-in Neovim 0.12.6/Linux pilot over the shared v1 subprocess protocol.
-- Selection coordinates saved buffers; it is not an OS sandbox. Pytest runs
-- trusted project code. This client never saves, stages, commits or publishes.
local M = {}
local uv = vim.uv
local active, last, review_job
local settings = { command = { 'henchman' }, cleanup_ms = 5000, review_ms = 10000 }
local epoch = 0
local FRAME, OUTPUT, REVIEW = 1048576, 131072, 524288 + 1
local null = vim.NIL
local cancel, settle, fail, check_buffers

local function absent(value) return value == nil or value == null end
local function identity(value)
  return type(value) == 'string' and #value > 0 and #value <= 128 and value:match('^[%w_.:@/%-]+$') ~= nil
end
local function integer(value)
  return type(value) == 'number' and value >= 1 and value <= 9007199254740991 and value == math.floor(value)
end
local function close_timer(timer)
  if timer then timer:stop(); if not timer:is_closing() then timer:close() end end
end
local function note(state, value)
  if #state.output >= OUTPUT then state.output_omitted = true; return end
  value = tostring(value)
  local remaining = OUTPUT - #state.output
  if #value > remaining then state.output_omitted = true end
  state.output = state.output .. value:sub(1, remaining)
end
local function scratch(title, content)
  local buffer = vim.api.nvim_create_buf(false, true)
  vim.bo[buffer].buftype, vim.bo[buffer].bufhidden = 'nofile', 'wipe'
  vim.bo[buffer].swapfile, vim.bo[buffer].modeline = false, false
  vim.api.nvim_buf_set_lines(buffer, 0, -1, false, vim.split(content, '\n', { plain = true }))
  vim.bo[buffer].modifiable = false
  vim.cmd('botright split')
  vim.api.nvim_win_set_buf(0, buffer)
  vim.api.nvim_buf_set_name(buffer, title .. ' ' .. tostring(buffer))
  vim.keymap.set('n', 'q', '<cmd>close<cr>', { buffer = buffer, silent = true })
  return buffer
end
local function review_text(payload)
  local text = 'Recorded changes for this run. Task verification is not asserted.\n'
  local omitted = false
  local function append(value)
    local room = OUTPUT - #text
    if #value > room then omitted = true end
    text = text .. value:sub(1, math.max(0, room))
  end
  for _, record in ipairs(payload.checkpoints) do
    append('\nCheckpoint ' .. tostring(record.checkpoint_id) .. '\n')
    if record.unavailable then append(tostring(record.unavailable) .. '\n') end
    for _, file in ipairs(record.files or {}) do
      append('\nFile: ' .. tostring(file.path) .. ' (' .. tostring(file.hunk_status) .. ')\n')
      for _, hunk in ipairs(file.hunks or {}) do
        append('@@ -' .. tostring(hunk.old_start) .. ' +' .. tostring(hunk.new_start) .. ' @@\n')
        append('Before:\n' .. tostring(hunk.before) .. '\nAfter:\n' .. tostring(hunk.after) .. '\n')
        if hunk.text_truncated then append('[Hunk text omitted at the service bound.]\n') end
      end
      if (file.hunks_omitted or 0) > 0 then append('[Additional hunks omitted.]\n') end
    end
  end
  if (payload.checkpoints_omitted or 0) > 0 then append('\n[Additional checkpoints omitted.]\n') end
  return text .. (omitted and '\n[Further review text omitted at the client display bound.]' or '')
end
local function send(state, method, params)
  if state.settled or state.exited or state.poisoned then return false end
  if state.request_count >= 32 then fail(state, 'Outstanding request limit reached'); return false end
  state.next_id = state.next_id + 1
  if not integer(state.next_id) then fail(state, 'Request limit reached'); return false end
  local frame = { v = 1, id = state.next_id, method = method, params = params }
  if method ~= 'initialize' then frame.connection_id = state.connection_id or null end
  local ok, raw = pcall(vim.json.encode, frame)
  if not ok or #raw > FRAME then fail(state, 'Request exceeds protocol bounds'); return false end
  local sent, count = pcall(vim.fn.chansend, state.job, raw .. '\n')
  if not sent or count == 0 then fail(state, 'Protocol input is unavailable'); return false end
  state.requests[frame.id], state.request_count = method, state.request_count + 1
  return frame.id
end
local function arm_stop(state)
  if state.stop_timer then return end
  state.stop_timer = uv.new_timer()
  state.stop_timer:start(state.cleanup_ms, 0, vim.schedule_wrap(function()
    if state.settled then return end
    state.transport_error = state.transport_error or 'Cleanup deadline expired; delivery is incomplete'
    state.pending = nil
    if not state.exited then pcall(vim.fn.jobstop, state.job) end
    -- The process/pipe callbacks still own settlement. A stop request is not a join.
    settle(state)
  end))
end
fail = function(state, message)
  if state.settled then return end
  state.transport_error = state.transport_error or message
  state.poisoned, state.pending = true, nil
  note(state, '\n' .. message .. '\n')
  pcall(vim.fn.jobstop, state.job)
  arm_stop(state)
end
local function release(state)
  close_timer(state.buffer_timer); close_timer(state.stop_timer)
  if state.group then pcall(vim.api.nvim_del_augroup_by_id, state.group) end
  for buffer, held in pairs(state.buffers) do
    if vim.api.nvim_buf_is_valid(buffer) then
      -- Restore options only; never replace live text with disk or model output.
      vim.bo[buffer].modifiable, vim.bo[buffer].autoread = held.modifiable, held.autoread
    end
  end
end
settle = function(state)
  if state.settled or not state.exited or not state.stdout_eof or not state.stderr_eof then return end
  state.pending = nil
  if state.partial ~= '' then state.transport_error = 'Incomplete protocol frame' end
  local terminal = state.terminal
  local expected = terminal and (terminal.status == 'completed' and 0 or terminal.status == 'cancelled' and 130 or 1)
  if state.transport_error or (terminal and state.exit_code ~= expected) then
    state.status = 'incomplete'
  elseif terminal then
    state.status = terminal.status
  elseif state.cancel_requested and not state.run_request_id and state.exit_code == 0 then
    state.status = 'cancelled_before_run'
  else state.status = 'incomplete' end
  state.settled = true
  release(state)
  if active == state then active = nil end
  last = state
  note(state, '\nRun: ' .. state.status .. '. Task verification is not asserted.\n')
  note(state, 'Saved disk changes can be inspected with HenchmanReview; buffers were not overwritten.\n')
  vim.notify('Henchman run: ' .. state.status .. '. Task verification is not asserted.')
end
local function hold(state, buffer)
  if not vim.api.nvim_buf_is_valid(buffer) or not vim.api.nvim_buf_is_loaded(buffer) then return true end
  local name = vim.api.nvim_buf_get_name(buffer)
  if not state.selected[uv.fs_realpath(name) or name] then return true end
  if state.buffers[buffer] then return true end
  if vim.bo[buffer].modified then return false end
  state.buffers[buffer] = { name = name, tick = vim.api.nvim_buf_get_changedtick(buffer),
    modifiable = vim.bo[buffer].modifiable, autoread = vim.bo[buffer].autoread }
  vim.bo[buffer].modifiable, vim.bo[buffer].autoread = false, false
  return true
end
check_buffers = function(state)
  if state.settled then return false end
  for buffer, held in pairs(state.buffers) do
    if not vim.api.nvim_buf_is_valid(buffer) or vim.api.nvim_buf_get_name(buffer) ~= held.name
      or vim.api.nvim_buf_get_changedtick(buffer) ~= held.tick or vim.bo[buffer].modified then
      state.buffer_conflict = true
      cancel(state)
      return false
    end
  end
  for _, buffer in ipairs(vim.api.nvim_list_bufs()) do
    if not hold(state, buffer) then state.buffer_conflict = true; cancel(state); return false end
  end
  return true
end
cancel = function(state)
  if not state or state.settled or state.cancel_requested then return end
  state.cancel_requested, state.pending, state.status = true, nil, 'cancelling'
  if state.run_request_id then
    send(state, 'cancel', { run_request_id = state.run_request_id, run_id = state.run_id or null })
  else send(state, 'shutdown', {}) end
  arm_stop(state)
end
local function decision(state, frame)
  local p = frame.payload
  if p.state ~= 'pending' then note(state, '\nUser input is unavailable.\n'); return end
  if state.pending or not identity(p.decision_id) or not integer(p.generation) or not state.run_id then
    fail(state, 'Invalid decision identity'); return
  end
  local pending = { id = p.decision_id, generation = p.generation, run_id = state.run_id }
  state.pending = pending
  local function answer(value)
    if active ~= state or state.pending ~= pending or state.settled or state.cancel_requested
      or not check_buffers(state) then return end
    if p.type == 'permission' and value == 'Inspect evidence' then
      M.show()
      vim.notify('Use HenchmanDecision after inspecting the evidence, or HenchmanCancel.')
      return
    end
    state.pending = nil
    local params = { session_id = state.session_id, run_id = pending.run_id,
      decision_id = pending.id, generation = pending.generation }
    if p.type == 'permission' then params.approved = value == 'Allow once'
    else
      if value ~= nil and (type(value) ~= 'string' or #value > 65536) then
        fail(state, 'Answer exceeds protocol bounds'); return
      end
      params.answer = value == nil and null or value
    end
    send(state, p.type .. '.respond', params)
  end
  pending.present = function()
    if active ~= state or state.pending ~= pending or state.cancel_requested then return end
    if p.type == 'permission' then
    vim.ui.select({ 'Deny', 'Inspect evidence', 'Allow once' }, {
      prompt = 'Henchman permission: ' .. tostring(p.tool_name or 'tool') .. ' (inspect HenchmanShow)',
    }, answer)
    else vim.ui.input({ prompt = tostring(p.question or 'Henchman question'):sub(1, 2048) .. ': ' }, answer) end
  end
  pending.present()
end
local function decode(raw)
  -- Neovim's decoder accepts duplicate keys and non-JSON numbers. Validate
  -- bounded JSON grammar and decoded key uniqueness before using that decoder.
  if #raw > FRAME then return nil end
  local index, length = 1, #raw
  local function char() return raw:sub(index, index) end
  local function space()
    while index <= length and char():match('[ \t\r\n]') do index = index + 1 end
  end
  local function string_token()
    if char() ~= '"' then return nil end
    local start = index
    index = index + 1
    while index <= length do
      local ch = char()
      if ch == '"' then index = index + 1; return raw:sub(start, index - 1) end
      if ch:byte() < 32 then return nil end
      if ch == '\\' then
        index = index + 1
        ch = char()
        if ch == 'u' then
          if not raw:sub(index + 1, index + 4):match('^%x%x%x%x$') then return nil end
          index = index + 4
        elseif ch == '' or not ('"\\/bfnrt'):find(ch, 1, true) then return nil end
      elseif ch:byte() >= 128 then
        local first, second, count = ch:byte(), raw:byte(index + 1), 0
        if first >= 194 and first <= 223 then count = 2
        elseif first >= 224 and first <= 239 then count = 3
        elseif first >= 240 and first <= 244 then count = 4
        else return nil end
        if not second or (first == 224 and second < 160) or (first == 237 and second > 159)
          or (first == 240 and second < 144) or (first == 244 and second > 143) then return nil end
        for offset = 1, count - 1 do
          local byte = raw:byte(index + offset)
          if not byte or byte < 128 or byte > 191 then return nil end
        end
        index = index + count - 1
      end
      index = index + 1
    end
  end
  local value
  value = function(depth)
    space()
    local ch = char()
    if ch == '{' or ch == '[' then
      if depth >= 16 then return false end
      local object, close, keys = ch == '{', ch == '{' and '}' or ']', {}
      index = index + 1; space()
      if char() == close then index = index + 1; return true end
      while true do
        if object then
          local token = string_token()
          if not token then return false end
          local ok, key = pcall(vim.json.decode, token)
          if not ok or type(key) ~= 'string' or keys[key] then return false end
          keys[key] = true
          space(); if char() ~= ':' then return false end
          index = index + 1
        end
        if not value(depth + 1) then return false end
        space()
        if char() == close then index = index + 1; return true end
        if char() ~= ',' then return false end
        index = index + 1; space()
      end
    elseif ch == '"' then return string_token() ~= nil
    elseif ch == 't' or ch == 'f' or ch == 'n' then
      local literal = ch == 't' and 'true' or ch == 'f' and 'false' or 'null'
      if raw:sub(index, index + #literal - 1) ~= literal then return false end
      index = index + #literal; return true
    else
      local start, whole = index, true
      if ch == '-' then index = index + 1 end
      if char() == '0' then index = index + 1
      elseif char():match('[1-9]') then
        repeat index = index + 1 until not char():match('%d')
      else return false end
      if char() == '.' then
        whole, index = false, index + 1
        if not char():match('%d') then return false end
        repeat index = index + 1 until not char():match('%d')
      end
      if char() == 'e' or char() == 'E' then
        whole, index = false, index + 1
        if char() == '+' or char() == '-' then index = index + 1 end
        if not char():match('%d') then return false end
        repeat index = index + 1 until not char():match('%d')
      end
      local number = tonumber(raw:sub(start, index - 1))
      return number ~= nil and number == number and math.abs(number) < math.huge
        and (not whole or math.abs(number) <= 9007199254740991)
    end
  end
  if not value(0) then return nil end
  space(); if index <= length then return nil end
  local ok, value = pcall(vim.json.decode, raw)
  return ok and value or nil
end
local function fields(value, required, optional)
  if type(value) ~= 'table' then return false end
  for key in pairs(required) do if value[key] == nil then return false end end
  for key in pairs(value) do if not required[key] and not (optional and optional[key]) then return false end end
  return true
end
local function terminal_valid(payload, run_id)
  -- Match ServerEncoder._result_payload; completion is never task verification.
  if not fields(payload, { status=true, runtime_status=true, task_verified=true, error=true }, { budget=true, recovery=true }) then return false end
  local statuses = { completed=true, failed=true, cancelled=true, incomplete=true, rejected=true }
  local runtimes = { completed=true, responded=true, no_work_done=true, stalled=true, timed_out=true, failed=true }
  if not statuses[payload.status] or payload.task_verified ~= false
    or (payload.runtime_status ~= null and not runtimes[payload.runtime_status]) then return false end
  if payload.error ~= null and (not fields(payload.error, { code=true, message=true })
    or not identity(payload.error.code) or type(payload.error.message) ~= 'string' or #payload.error.message > 4096) then return false end
  if payload.status == 'completed' and (absent(run_id) or payload.error ~= null
    or (payload.runtime_status ~= 'completed' and payload.runtime_status ~= 'responded')) then return false end
  if payload.status == 'rejected' and (not absent(run_id) or payload.runtime_status ~= null) then return false end
  return true
end
local function frame_received(state, raw)
  if state.poisoned then return end
  local frame = decode(raw)
  if not fields(frame, { v=true, seq=true, kind=true, request_id=true, session_id=true, run_id=true, payload=true })
    or frame.v ~= 1 or not integer(frame.seq) or frame.seq ~= state.seq + 1
    or type(frame.payload) ~= 'table' or state.terminal then fail(state, 'Invalid or out-of-order protocol frame'); return end
  state.seq = frame.seq
  if (frame.request_id ~= null and not integer(frame.request_id))
    or (frame.session_id ~= null and not identity(frame.session_id))
    or (frame.run_id ~= null and (not identity(frame.run_id) or frame.session_id == null)) then
    fail(state, 'Invalid protocol identity'); return
  end
  if state.session_id and frame.session_id ~= state.session_id then fail(state, 'Session identity changed'); return end
  if state.run_id and state.run_id ~= frame.run_id then fail(state, 'Run identity changed'); return end
  local p = frame.payload
  local method = state.requests[frame.request_id]
  if frame.kind == 'response' then
    if not method or method ~= p.method or method == 'run' or method == 'shutdown' then fail(state, 'Unowned response'); return end
    state.requests[frame.request_id], state.request_count = nil, state.request_count - 1
    if method ~= 'initialize' then
      if p.state ~= (method == 'cancel' and 'requested' or 'received') then fail(state, 'Invalid control response'); return end
      if frame.run_id ~= null then state.run_id = frame.run_id end
      return
    end
    if state.connection_id or frame.request_id ~= 1 or frame.run_id ~= null or not identity(p.connection_id) or not identity(frame.session_id) then
      fail(state, 'Invalid initialization response'); return
    end
    if state.requested_session.mode == 'resume' and frame.session_id ~= state.requested_session.id then
      fail(state, 'Requested session identity changed'); return
    end
    state.connection_id, state.session_id = p.connection_id, frame.session_id
    if state.cancel_requested or not check_buffers(state) then return end
    state.status = 'running'
    state.run_request_id = send(state, 'run', { session_id = state.session_id, prompt = state.prompt, agent = null })
    state.prompt = nil
  elseif frame.kind == 'event' then
    if not state.run_request_id or frame.request_id ~= state.run_request_id or frame.run_id == null then fail(state, 'Unowned event'); return end
    state.run_id = frame.run_id
    check_buffers(state)
    note(state, vim.json.encode(p) .. '\n')
    if (p.type == 'permission' or p.type == 'question') and not state.cancel_requested then decision(state, frame) end
  elseif frame.kind == 'result' then
    if not state.run_request_id or frame.request_id ~= state.run_request_id or not terminal_valid(p, frame.run_id) then fail(state, 'Invalid terminal result'); return end
    if frame.run_id ~= null then state.run_id = frame.run_id end
    state.requests, state.request_count = {}, 0
    state.terminal, state.pending = p, nil
    state.status = 'finishing'
    if type(p.error) == 'table' and type(p.error.message) == 'string' then note(state, p.error.message .. '\n') end
    arm_stop(state)
  elseif frame.kind == 'error' then
    if (frame.request_id ~= null and not method) or not fields(p, { code=true, message=true })
      or not identity(p.code) or type(p.message) ~= 'string' then fail(state, 'Unowned protocol error'); return end
    if method then state.requests[frame.request_id], state.request_count = nil, state.request_count - 1 end
    note(state, 'Protocol error: ' .. tostring(p.code or 'unknown') .. '\n')
    state.protocol_error = true
    arm_stop(state)
  else fail(state, 'Unknown protocol envelope') end
end
local function stdout(state, data)
  if state.stdout_eof then return end
  if #data == 1 and data[1] == '' then state.stdout_eof = true; settle(state); return end
  for index, text in ipairs(data) do
    if #state.partial + #text > FRAME then fail(state, 'Protocol frame exceeds byte limit'); return end
    state.partial = state.partial .. text
    if index < #data then
      frame_received(state, state.partial)
      state.partial = ''
      if state.poisoned then return end
    end
  end
end
local function validate(opts)
  local version = vim.version()
  if uv.os_uname().sysname ~= 'Linux' or version.major ~= 0 or version.minor ~= 12 or version.patch ~= 6 then
    return nil, 'This pilot supports Neovim 0.12.6 on Linux'
  end
  if type(opts.session) ~= 'table' or (opts.session.mode ~= 'new' and opts.session.mode ~= 'resume')
    or (opts.session.mode == 'resume' and not identity(opts.session.id)) then return nil, 'Choose an explicit new or resume session' end
  if type(opts.prompt) ~= 'string' or not opts.prompt:find('%S') or #opts.prompt > 262144 then return nil, 'Provide a bounded task prompt' end
  if type(opts.project) ~= 'string' then return nil, 'Choose an explicit project directory' end
  local root = uv.fs_realpath(opts.project)
  if not root or type(opts.paths) ~= 'table' or #opts.paths < 1 or #opts.paths > 256 then return nil, 'Select 1–256 saved project files' end
  local selected, paths = {}, {}
  for _, value in ipairs(opts.paths) do
    if type(value) ~= 'string' then return nil, 'Invalid selected path' end
    local path = vim.fs.normalize(value:sub(1, 1) == '/' and value or root .. '/' .. value)
    local info = uv.fs_lstat(path)
    if path:sub(1, #root + 1) ~= root .. '/' or uv.fs_realpath(path) ~= path or not info or info.type ~= 'file'
      or info.nlink ~= 1 or selected[path] then return nil, 'Selection requires distinct saved regular project files without links' end
    selected[path] = true; paths[#paths + 1] = path
  end
  local command = opts.command or settings.command
  if type(command) ~= 'table' or #command < 1 then return nil, 'Configure an argv command' end
  for _, arg in ipairs(command) do if type(arg) ~= 'string' or arg:find('\0', 1, true) then return nil, 'Invalid argv command' end end
  return { root = root, selected = selected, paths = paths, command = vim.deepcopy(command) }
end
function M.run(opts)
  if active or review_job then return false, 'An owned run or review is still active' end
  opts = opts or {}
  local selection, reason = validate(opts)
  if not selection then return false, reason end
  epoch = epoch + 1
  local state = { generation = epoch, project = selection.root, selected = selection.selected, buffers = {},
    command = selection.command, requested_session = vim.deepcopy(opts.session), requests = {}, request_count = 0,
    next_id = 0, seq = 0, output = '', partial = '', status = 'starting',
    settled = false, task_verified = false, prompt = opts.prompt, stderr_bytes = 0, cleanup_ms = settings.cleanup_ms }
  for _, buffer in ipairs(vim.api.nvim_list_bufs()) do
    if not hold(state, buffer) then release(state); return false, 'Unsaved selected buffer; save or remove it from the selection' end
  end
  local argv = vim.deepcopy(selection.command)
  vim.list_extend(argv, { 'headless', '--protocol-version', '1', '--project', selection.root })
  for _, path in ipairs(selection.paths) do vim.list_extend(argv, { '--editor-path', path }) end
  active, last = state, state
  local started, job = pcall(vim.fn.jobstart, argv, { cwd = selection.root, pty = false,
    on_stdout = function(_, data) stdout(state, data) end,
    on_stderr = function(_, data)
      if #data == 1 and data[1] == '' then state.stderr_eof = true; settle(state)
      else state.stderr_bytes = math.min(65537, state.stderr_bytes + #table.concat(data, '\n')) end
    end,
    on_exit = function(_, code)
      state.exited, state.exit_code = true, code
      arm_stop(state); settle(state)
    end,
  })
  state.job = started and job or -1
  if state.job <= 0 then active = nil; release(state); state.settled, state.status = true, 'incomplete'; return false, 'Could not start Henchman' end
  state.group = vim.api.nvim_create_augroup('HenchmanOwnedRun' .. epoch, { clear = true })
  vim.api.nvim_create_autocmd({ 'BufReadPost', 'BufFilePost', 'TextChanged', 'TextChangedI', 'BufDelete' }, {
    group = state.group, callback = function() if active == state then check_buffers(state) end end,
  })
  state.buffer_timer = uv.new_timer()
  state.buffer_timer:start(50, 50, vim.schedule_wrap(function() if active == state then check_buffers(state) end end))
  send(state, 'initialize', { session = opts.session, interactive = { permissions = true, questions = true } })
  return true
end
function M.cancel() epoch = epoch + 1; cancel(active) end
function M.decision()
  if active and active.pending then active.pending.present() end
end
function M.status()
  local state = active or last
  if not state then return nil end
  return { status = state.status, settled = state.settled, session_id = state.session_id, run_id = state.run_id,
    exit_code = state.exit_code, task_verified = false, output = state.output, output_omitted = state.output_omitted or false,
    runtime_result = state.terminal and vim.deepcopy(state.terminal) or nil, transport_error = state.transport_error,
    buffer_conflict = state.buffer_conflict or false, diagnostics_received = state.stderr_bytes > 0 }
end
function M.show()
  local state = M.status()
  if not state then return end
  scratch('Henchman evidence', 'Run: ' .. state.status .. '\nTask verification is not asserted.\n\n'
    .. state.output .. (state.output_omitted and '\n[Further evidence was omitted at the display bound.]' or '')
    .. (state.diagnostics_received and '\n[Process stderr was received; raw startup diagnostics are not displayed.]' or ''))
end
function M.review(callback)
  if active or review_job then return false, 'Wait for the owned run/review to settle' end
  if not last or not last.run_id then return false, 'No actual run is available for review' end
  local state = last
  local argv = vim.deepcopy(state.command)
  vim.list_extend(argv, { 'checkpoint', 'review-run', state.run_id })
  local child = { output = '', eof = false, stderr_eof = false, stopped = false }
  review_job = child
  local function finish()
    if child.finished or not child.exited or not child.eof or not child.stderr_eof then return end
    child.finished = true
    close_timer(child.timer)
    if review_job == child then review_job = nil end
    local result = not child.stopped and child.code == 0 and decode(child.output) or nil
    if type(result) ~= 'table' or type(result.checkpoints) ~= 'table' or result.task_verified ~= false then result = nil end
    if callback then callback(result, result and nil or 'Checkpoint review unavailable or incomplete')
    elseif result then scratch('Henchman recorded diff', review_text(result))
    else vim.notify('Checkpoint review unavailable or incomplete', vim.log.levels.WARN) end
  end
  local started, job = pcall(vim.fn.jobstart, argv, { cwd = state.project, pty = false,
    on_stdout = function(_, data)
      if #data == 1 and data[1] == '' then child.eof = true; finish(); return end
      local chunk = table.concat(data, '\n')
      if #child.output + #chunk > REVIEW then child.stopped = true; pcall(vim.fn.jobstop, child.job)
      elseif not child.stopped then child.output = child.output .. chunk end
    end,
    on_stderr = function(_, data) if #data == 1 and data[1] == '' then child.stderr_eof = true; finish() end end,
    on_exit = function(_, code) child.exited, child.code = true, code; finish() end,
  })
  child.job = started and job or -1
  if child.job <= 0 then review_job = nil; return false, 'Could not start review' end
  child.timer = uv.new_timer()
  child.timer:start(settings.review_ms, 0, vim.schedule_wrap(function()
    child.stopped = true; pcall(vim.fn.jobstop, child.job)
  end))
  return true
end
function M.shutdown()
  epoch = epoch + 1
  if review_job then
    local child = review_job
    child.stopped = true
    pcall(vim.fn.jobstop, child.job)
    vim.wait(2500, function() return child.finished == true end, 10)
  end
  if active then
    local state = active
    cancel(state)
    vim.wait(state.cleanup_ms, function() return state.settled end, 10)
    if not state.settled then fail(state, 'Editor shutdown interrupted delivery'); vim.fn.jobwait({ state.job }, 2500) end
  end
end
function M.setup(opts)
  epoch = epoch + 1
  opts = opts or {}
  if opts.command then settings.command = vim.deepcopy(opts.command) end
  if opts.project then settings.project = opts.project end
  if opts.paths then settings.paths = vim.deepcopy(opts.paths) end
  for _, key in ipairs({ 'cleanup_ms', 'review_ms' }) do
    if opts[key] ~= nil then assert(integer(opts[key]) and opts[key] <= 30000, 'Invalid client deadline'); settings[key] = opts[key] end
  end
  local function start(session, prompt)
    epoch = epoch + 1
    local ticket = epoch
    local project, command = settings.project, vim.deepcopy(settings.command)
    local paths = vim.deepcopy(settings.paths or { vim.api.nvim_buf_get_name(0) })
    local function begin(value)
      if not value or ticket ~= epoch then return end
      local ok, reason = M.run({ project = project, command = command, paths = paths,
        session = session, prompt = value })
      if not ok then vim.notify(reason, vim.log.levels.WARN) end
    end
    if prompt ~= '' then begin(prompt) else vim.ui.input({ prompt = 'Henchman task: ' }, begin) end
  end
  vim.api.nvim_create_user_command('HenchmanNew', function(args) start({ mode = 'new' }, args.args) end, { nargs = '*', force = true })
  vim.api.nvim_create_user_command('HenchmanResume', function(args)
    start({ mode = 'resume', id = args.fargs[1] }, table.concat(args.fargs, ' ', 2))
  end, { nargs = '+', force = true })
  vim.api.nvim_create_user_command('HenchmanSelect', function(args) settings.paths = vim.deepcopy(args.fargs) end, { nargs = '+', complete = 'file', force = true })
  vim.api.nvim_create_user_command('HenchmanCancel', M.cancel, { force = true })
  vim.api.nvim_create_user_command('HenchmanDecision', M.decision, { force = true })
  vim.api.nvim_create_user_command('HenchmanShow', M.show, { force = true })
  vim.api.nvim_create_user_command('HenchmanReview', function()
    local ok, reason = M.review(); if not ok then vim.notify(reason, vim.log.levels.WARN) end
  end, { force = true })
  local group = vim.api.nvim_create_augroup('HenchmanClient', { clear = true })
  vim.api.nvim_create_autocmd('VimLeavePre', { group = group, callback = M.shutdown })
end
return M
