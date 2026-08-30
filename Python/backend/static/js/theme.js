const THEME_KEY = "theme";

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

function setActiveButton(buttons, theme) {
  buttons.forEach((button) => {
    button.classList.toggle("active", button.dataset.theme === theme);
  });
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY) || "system";
  applyTheme(stored);

  const buttons = Array.from(document.querySelectorAll("#theme-toggle button"));
  setActiveButton(buttons, stored);

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const theme = button.dataset.theme;
      localStorage.setItem(THEME_KEY, theme);
      applyTheme(theme);
      setActiveButton(buttons, theme);
    });
  });
}

initTheme();
