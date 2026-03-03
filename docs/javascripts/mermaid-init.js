// Mermaid initialization for MkDocs
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Mermaid
    mermaid.initialize({
        startOnLoad: true,
        theme: 'dark',
        securityLevel: 'loose',
        flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
            curve: 'basis'
        },
        sequence: {
            useMaxWidth: true,
            height: 40
        },
        gantt: {
            useMaxWidth: true
        }
    });
    
    // Re-render Mermaid diagrams when tabs are switched
    document.querySelectorAll('.tabbed-set').forEach(function(tabSet) {
        tabSet.addEventListener('click', function() {
            setTimeout(function() {
                mermaid.init(undefined, document.querySelectorAll('.mermaid'));
            }, 100);
        });
    });
    
    // Re-render Mermaid diagrams when details are toggled
    document.querySelectorAll('details').forEach(function(details) {
        details.addEventListener('toggle', function() {
            if (this.open) {
                setTimeout(function() {
                    mermaid.init(undefined, document.querySelectorAll('.mermaid'));
                }, 100);
            }
        });
    });
});