/**
 * Theme Sync — Synchronizes the Hive UI theme with MkDocs Material.
 *
 * Listens for postMessage events from the parent window (Hive UI) and
 * applies the corresponding MkDocs Material color scheme + CSS overrides.
 */
(function () {
  "use strict";

  var DARK_THEMES = ["ember", "slate", "signal", "hacker", "star-trek", "cyberpunk"];
  var LIGHT_THEMES = ["office", "minimal"];

  /**
   * Apply a Hive UI theme to MkDocs Material.
   * Sets the color-scheme attribute and a data-hive-theme attribute
   * that the companion CSS file uses for fine-grained overrides.
   */
  function applyTheme(name) {
    if (!name) return;

    var isDark = DARK_THEMES.indexOf(name) !== -1;
    var isLight = LIGHT_THEMES.indexOf(name) !== -1;
    if (!isDark && !isLight) return;

    var body = document.body;

    // Set Material scheme (slate = dark, default = light)
    body.setAttribute("data-md-color-scheme", isDark ? "slate" : "default");

    // Set hive theme for CSS overrides
    body.setAttribute("data-hive-theme", name);

    // Remove Material's own primary/accent data attributes so they don't
    // compete with our CSS custom-property overrides
    body.removeAttribute("data-md-color-primary");
    body.removeAttribute("data-md-color-accent");

    // Hide the built-in palette toggle — parent controls theme
    var toggle = document.querySelector(".md-header__option");
    if (toggle) toggle.style.display = "none";
  }

  // Listen for theme-sync messages from parent window
  window.addEventListener("message", function (event) {
    if (event.data && event.data.type === "theme-sync" && event.data.theme) {
      applyTheme(event.data.theme);
    }
  });

  // On load, request theme from parent
  document.addEventListener("DOMContentLoaded", function () {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: "theme-request" }, "*");
    }
  });
})();
