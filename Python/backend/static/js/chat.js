function generateThreadId() {
  // crypto.randomUUID() only exists in secure contexts (https:// or
  // http://localhost) -- accessing this app over plain http:// via a LAN
  // IP silently breaks the whole script at this line otherwise, since
  // crypto.randomUUID is simply undefined there.
  if (window.crypto && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const threadId = generateThreadId();

function appendMessage(role, text) {
  const log = document.getElementById("chat-log");
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = text;
  log.appendChild(message);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showTyping() {
  const log = document.getElementById("chat-log");
  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.id = "typing-indicator";
  indicator.innerHTML = "<span></span><span></span><span></span>";
  log.appendChild(indicator);
  log.scrollTop = log.scrollHeight;
}

function hideTyping() {
  const indicator = document.getElementById("typing-indicator");
  if (indicator) indicator.remove();
}

function setInputDisabled(disabled) {
  document.getElementById("chat-input").disabled = disabled;
  document.querySelector("#chat-form button").disabled = disabled;
  document
    .querySelectorAll("#pending-action-buttons button")
    .forEach((button) => {
      button.disabled = disabled;
    });
}

function showPendingAction(title, contentHtml, buttons) {
  const panel = document.getElementById("pending-action");
  document.getElementById("pending-action-title").textContent = title;
  document.getElementById("pending-action-content").innerHTML = contentHtml;

  const buttonRow = document.getElementById("pending-action-buttons");
  buttonRow.innerHTML = "";
  buttons.forEach(({ label, primary, onClick }) => {
    const button = document.createElement("button");
    button.textContent = label;
    if (primary) button.className = "primary";
    if (onClick) button.addEventListener("click", onClick);
    buttonRow.appendChild(button);
  });

  panel.hidden = false;
}

function hidePendingAction() {
  document.getElementById("pending-action").hidden = true;
}

async function callAgent(body) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 310000);

  setInputDisabled(true);
  showTyping();

  try {
    const response = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, ...body }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      appendMessage(
        "agent",
        errorBody.detail || "Something went wrong. Please try again.",
      );
      return null;
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    appendMessage(
      "agent",
      "The request timed out or failed. Please try again.",
    );
    return null;
  } finally {
    hideTyping();
    setInputDisabled(false);
  }
}

function handleAgentResponse(data) {
  if (!data) return;

  if (data.status === "busy") {
    appendMessage(
      "agent",
      data.detail || "Still working on your previous request — please wait.",
    );
    return;
  }

  if (data.status === "done") {
    appendMessage("agent", data.summary);
    hidePendingAction();
    return;
  }

  if (data.status === "interrupted") {
    renderInterrupt(data.interrupt);
  }
}

function specChip(label, value) {
  return `<span class="spec-chip">${label}: ${value ?? "?"}</span>`;
}

function renderInterrupt(interrupt) {
  if (interrupt.type === "confirm_requirements") {
    const req = interrupt.requirements;
    const content = `
            <p>Max price: ${req.max_price ?? "any"}</p>
            <p>Vehicle style: ${req.vehicle_style ?? "any"}</p>
            <p>Fuel type: ${req.fuel_type ?? "any"}</p>
            <p>Must-haves: ${(req.must_haves || []).map(escapeHtml).join(", ") || "none"}</p>
        `;
    showPendingAction("Confirm your requirements", content, [
      {
        label: "Approve",
        primary: true,
        onClick: () => sendResume({ action: "approve" }),
      },
      { label: "Refine", onClick: promptRefine },
    ]);
  } else if (interrupt.type === "human_review") {
    const comparison = interrupt.comparison;
    const cars = comparison.cars
      .map(
        (car) => `
                    <div class="car-summary">
                        <div class="car-title">${car.make} ${car.model} (${car.year})</div>
                        <div class="spec-chips">
                            ${specChip("MSRP", car.msrp != null ? `$${car.msrp}` : null)}
                            ${specChip("Hwy MPG", car.highway_mpg)}
                            ${specChip("City MPG", car.city_mpg)}
                            ${specChip("HP", car.horsepower)}
                        </div>
                        <ul>${car.pros.map((p) => `<li class="pro">+ ${escapeHtml(p)}</li>`).join("")}${car.cons
                          .map((c) => `<li class="con">- ${escapeHtml(c)}</li>`)
                          .join("")}</ul>
                    </div>
                `,
      )
      .join("");
    const notes = comparison.notes
      ? `<p><em>${escapeHtml(comparison.notes)}</em></p>`
      : "";
    showPendingAction("Review your comparison", cars + notes, [
      {
        label: "Approve",
        primary: true,
        onClick: () => sendResume({ action: "approve" }),
      },
      {
        label: "Save shortlist",
        onClick: () => sendResume({ action: "save" }),
      },
      { label: "Refine", onClick: promptRefine },
    ]);
  } else if (interrupt.type === "confirm_save") {
    showPendingAction(interrupt.message || "Confirm save", "", [
      {
        label: "Confirm",
        primary: true,
        onClick: () => sendResume({ action: "confirm" }),
      },
      { label: "Decline", onClick: () => sendResume({ action: "decline" }) },
    ]);
  }
}

function promptRefine() {
  const refinement = window.prompt("What would you like to change?");
  if (refinement === null) return;
  sendResume({ action: "refine", refinement });
}

async function sendResume(resume) {
  hidePendingAction();
  const data = await callAgent({ resume });
  handleAgentResponse(data);
}

document
  .getElementById("chat-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;

    appendMessage("user", text);
    input.value = "";

    const data = await callAgent({ message: text });
    handleAgentResponse(data);
  });

appendMessage(
  "agent",
  "Hi! Tell me what kind of car you're looking for and I'll help you research it.",
);
