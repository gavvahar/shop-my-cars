function appendMessage(role, text) {
  const log = document.getElementById("chat-log");
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  log.appendChild(message);
  log.scrollTop = log.scrollHeight;
}

function showPendingAction(title, contentHtml, buttons) {
  const panel = document.getElementById("pending-action");
  document.getElementById("pending-action-title").textContent = title;
  document.getElementById("pending-action-content").innerHTML = contentHtml;

  const buttonRow = document.getElementById("pending-action-buttons");
  buttonRow.innerHTML = "";
  buttons.forEach(({ label, primary }) => {
    const button = document.createElement("button");
    button.textContent = label;
    if (primary) button.className = "primary";
    buttonRow.appendChild(button);
  });

  panel.hidden = false;
}

function hidePendingAction() {
  document.getElementById("pending-action").hidden = true;
}

document.getElementById("chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text);
  input.value = "";

  // Task 12 replaces this with a real fetch() to /api/agent.
});

// Scaffold demo (Task 11 only) — proves the page renders correctly.
// Task 12 drives appendMessage/showPendingAction from real /api/agent
// responses instead of this hardcoded line.
appendMessage(
  "agent",
  "Hi! Tell me what kind of car you're looking for and I'll help you research it.",
);
