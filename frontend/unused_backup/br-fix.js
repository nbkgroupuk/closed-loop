/* br-fix.js - safe fallback for updateTerminalStatus (won't change layout) */
(function(){
  if (typeof updateTerminalStatus === 'undefined') {
    window.updateTerminalStatus = function(statusObj){
      try {
        const dot = document.querySelector('#server-status-dot');
        const label = document.querySelector('#server-status-label');
        // keep behaviour minimal and non-breaking
        if (dot) dot.style.background = (statusObj && statusObj.online) ? '#33cc33' : '#cc3333';
        if (label) label.textContent = (statusObj && statusObj.message)
          ? statusObj.message
          : ((statusObj && statusObj.online) ? 'Online' : 'Offline');
      } catch(e) { /* intentionally no-op */ }
    };
  }
})();
