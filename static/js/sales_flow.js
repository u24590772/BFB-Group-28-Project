/* =========================================================
   FinFlow – sales_flow.js
   Advance step asks Flask to move the order on
   (POST /api/sales-flow/<id>/advance), then updates the row
   and the board without reloading the page.
   ========================================================= */

const flowBody = document.getElementById("flow-body");
const statusMessage = document.getElementById("flow-status");
const squares = document.querySelectorAll(".track-step");

// Count the orders on each step and write the count on the board.
function updateBoard() {
  const counts = [0, 0, 0, 0, 0, 0, 0];
  for (const row of flowBody.querySelectorAll("tr[data-step]")) {
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

// Show the server's answer in the row.
function updateRow(row, data) {
  row.dataset.step = data.new_step;

  const badge = row.querySelector(".badge");
  badge.className = "badge stage-" + data.new_step;
  badge.textContent = "Step " + data.new_step + ": " + data.step_name;

  row.querySelector(".next-action").textContent = data.next_action;
}

// Runs when an "Advance step" button is clicked.
async function advanceOrder(event) {
  const button = event.target;
  const row = button.closest("tr");
  const orderRef = row.cells[0].textContent;

  // Loading state: stop double clicks while Flask works
  button.disabled = true;
  button.textContent = "Saving…";
  statusMessage.classList.remove("is-error");

  try {
    const response = await fetch("/api/sales-flow/" + row.dataset.orderId + "/advance", {
      method: "POST"
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message);
    }

    // Success state
    updateRow(row, data);
    updateBoard();

    let message = orderRef + " moved to step " + data.new_step + ": " + data.step_name + ".";
    if (data.waybills.length > 0) {
      message += " Waybills: " + data.waybills.join(", ");
    }
    statusMessage.textContent = message;
    flash(row);
    flash(squares[data.new_step - 1]);

    if (data.is_dispatched) {
      button.textContent = "Dispatched"; // stays disabled
    } else {
      button.disabled = false;
      button.textContent = "Advance step";
    }
  } catch (error) {
    // Error state: say what went wrong and let the user try again
    statusMessage.textContent = "Couldn't move " + orderRef + ": " + error.message;
    statusMessage.classList.add("is-error");
    button.disabled = false;
    button.textContent = "Advance step";
  }
}

// Connect every Advance step button when the page loads.
for (const button of document.querySelectorAll(".advance-btn")) {
  button.addEventListener("click", advanceOrder);
}
