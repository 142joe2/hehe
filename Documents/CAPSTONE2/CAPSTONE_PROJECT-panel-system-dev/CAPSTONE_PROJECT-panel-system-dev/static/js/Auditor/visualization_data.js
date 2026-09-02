/* Auditor dashboard visualizations.
   All overview charts/panels (Payment Status donut, Department Compliance,
   Audit Pipeline, strip, KPIs, queue) are owned and rendered by the inline
   overview script inside auditor_dashboard.html via loadAuditorOverview(),
   which fetches every endpoint once in a single parallel Promise.all and
   renders immediately. Rendering the same canvases here as well caused
   duplicate API calls and charts fighting each other (slow "Loading...").
   This module intentionally stays idle. */
(function () {
  "use strict";
  function initAuditorVisualizations() {
    /* no-op — handled by the inline overview renderer */
  }
  window.initAuditorVisualizations = initAuditorVisualizations;
})();
