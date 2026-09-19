/* 导航栏明暗主题切换：高亮当前模块 + 与 iframe 内页面联动
 * 参考 workspace-demo/shell.js，适配 web-tools 的 iframe(id=contentFrame) 与按钮(id=themeToggle)
 */
(function () {
  "use strict";

  const THEME_KEY = "shell_theme";
  const root = document.documentElement;
  const btn = document.getElementById("themeToggle");
  const icon = btn && btn.querySelector(".tt-icon");
  const label = btn && btn.querySelector(".tt-label");
  const frame = document.getElementById("contentFrame");

  // 把外壳主题同步到 iframe 内的页面
  function propagateTheme(theme) {
    if (!frame) return;
    try {
      const doc = frame.contentDocument;
      if (doc && doc.documentElement) doc.documentElement.setAttribute("data-theme", theme);
    } catch (e) {}
    try {
      if (frame.contentWindow) {
        frame.contentWindow.postMessage({ source: "workbench", type: "theme", theme: theme }, "*");
      }
    } catch (e) {}
  }

  function renderTheme(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (icon) icon.textContent = theme === "light" ? "☀️" : "🌙";
    if (label) label.textContent = theme === "light" ? "浅色" : "深色";
    if (persist) {
      try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
    }
    propagateTheme(theme);
  }

  // 初始化为已保存（或默认）主题，与 <head> 内联脚本一致
  renderTheme(root.getAttribute("data-theme") || "dark", false);

  if (btn) {
    btn.addEventListener("click", function () {
      const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      renderTheme(next, true);
    });
  }

  // iframe 每次加载（切换模块）后，把当前外壳主题推给它
  if (frame) {
    frame.addEventListener("load", function () {
      propagateTheme(root.getAttribute("data-theme") || "dark");
    });
  }

  // 接收 iframe 内页面自己的主题切换，使导航按钮保持一致
  window.addEventListener("message", function (e) {
    const d = e.data;
    if (d && d.source === "module" && d.type === "theme" && d.theme) {
      renderTheme(d.theme, true);
    }
  });
})();
