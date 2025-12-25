document.addEventListener("DOMContentLoaded", () => {
  const notifyAudio = new Audio("/static/audio/notify.mp3");

  const timers = document.querySelectorAll(".timer-start");
  timers.forEach((btn) => {
    btn.addEventListener("click", () => {
      const duration = parseInt(btn.dataset.duration || "0", 10);
      if (!duration || duration <= 0) return;
      const display = btn.parentElement.querySelector(".timer-display");
      let remaining = duration;
      btn.disabled = true;
      display.textContent = `${remaining}s`;
      const interval = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(interval);
          display.textContent = "Done!";
          btn.disabled = false;
          notifyAudio.play().catch(() => {});
          return;
        }
        display.textContent = `${remaining}s`;
      }, 1000);
    });
  });

  document.querySelectorAll(".play-complete-sound").forEach((btn) => {
    btn.addEventListener("click", () => {
      notifyAudio.play().catch(() => {});
    });
  });
});
