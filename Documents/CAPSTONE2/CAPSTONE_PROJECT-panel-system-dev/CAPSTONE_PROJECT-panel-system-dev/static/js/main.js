document.addEventListener("turbo:load", () => {
  const toggleButton = document.querySelector("[data-nav-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");

  if (!toggleButton || !navLinks) {
    return;
  }

  toggleButton.addEventListener("click", () => {
    navLinks.classList.toggle("is-open");
  });
});
