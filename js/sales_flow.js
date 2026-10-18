/* =========================================================
   FinFlow – sales_flow.js
   Moves orders through the 7 steps of the Takealot sales flow.
   Milestone 1: runs in the browser only (resets on reload).
   Milestone 2: the button will call the Flask API instead.
   ========================================================= */

// The 7 steps from Sales Flow.png, in order.
// "next" is the job that moves an order on to the following step.
const STAGES = [
  { name: "Takealot PO Created",           next: "Confirm PO on Takealot Websupplier" },
  { name: "Fintr Confirms on Websupplier", next: "Create Sales Order on ERPNext" },
  { name: "Sales Order on ERPNext",        next: "Create Delivery Note on ERPNext" },
  { name: "Delivery Note on ERPNext",      next: "Create Shipment on Websupplier" },
  { name: "Shipment on Websupplier",       next: "Book Shipment on Courier Guy" },
  { name: "Shipment on Courier Guy",       next: "Hand cartons to the courier" },
  { name: "Dispatched",                    next: "None – order complete" }
];
const LAST_STEP = STAGES.length; // 7

const flowBody = document.getElementById("flow-body");
const statusMessage = document.getElementById("flow-status");
const squares = document.querySelectorAll(".track-step");

// Fill in one row's badge, next action and button for its current step.
function renderRow(row) {
  const step = Number(row.dataset.step);
  const stage = STAGES[step - 1];

  const badge = row.querySelector(".badge");
  badge.className = "badge stage-" + step;
  badge.textContent = "Step " + step + ": " + stage.name;

  row.querySelector(".next-action").textContent = stage.next;

  if (step === LAST_STEP) {
    const button = row.querySelector(".advance-btn");
    button.disabled = true;
    button.textContent = "Dispatched";
  }
}

// Count the orders on each step and write the count on the board.
function updateBoard() {
  const counts = [0, 0, 0, 0, 0, 0, 0];
  for (const row of flowBody.rows) {
    counts[Number(row.dataset.step) - 1] += 1;
  }

  squares.forEach(function (square, index) {
    const label = square.querySelector(".track-count");
    const count = counts[index];

    if (count === 0) {
      label.textContent = "No orders";
    } else if (count === 1) {
      label.textContent = "1 order";
    } else {
      label.textContent = count + " orders";
    }
    label.classList.toggle("is-empty", count === 0);
  });
}

// Briefly highlight something that just changed.
function flash(element) {
  element.animate(
    [{ backgroundColor: "#FFF1C2" }, { backgroundColor: "transparent" }],
    { duration: 1200, easing: "ease-out" }
  );
}

// Runs when an "Advance step" button is clicked.
function advanceOrder(event) {
  const row = event.target.closest("tr");
  const step = Number(row.dataset.step);
  if (step >= LAST_STEP) {
    return; // already dispatched
  }

  const newStep = step + 1;
  row.dataset.step = newStep;
  renderRow(row);
  updateBoard();

  const orderId = row.cells[0].textContent;
  statusMessage.textContent =
    orderId + " moved to step " + newStep + ": " + STAGES[newStep - 1].name + ".";
  flash(row);
  flash(squares[newStep - 1]);
}

// Set up the page when it loads.
for (const row of flowBody.rows) {
  renderRow(row);
  row.querySelector(".advance-btn").addEventListener("click", advanceOrder);
}
updateBoard();