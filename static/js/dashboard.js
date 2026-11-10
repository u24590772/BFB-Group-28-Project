/* =========================================================
   FinFlow – dashboard.js
   Handles interactive Order Intake (Flow 2) and
   Master Carton & Courier Freight Calculator (Flow 3)
   without reloading the page.
   ========================================================= */

// 1. Order Intake Form (Flow 2)
const orderForm = document.getElementById("order-form");
const orderFeedback = document.getElementById("order-feedback");
const submitOrderBtn = document.getElementById("submit-order-btn");
const ordersBody = document.getElementById("orders-body");

if (orderForm) {
  orderForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const orderRefInput = document.getElementById("order-ref");
    const channelInput = document.getElementById("order-channel");
    const qtyInput = document.getElementById("order-qty");

    const orderRef = orderRefInput.value.trim();
    const channel = channelInput.value;
    const quantity = parseInt(qtyInput.value, 10);

    if (!orderRef || isNaN(quantity) || quantity <= 0) {
      orderFeedback.textContent = "Please provide a valid order reference and positive quantity.";
      orderFeedback.className = "flow-status is-error";
      return;
    }

    submitOrderBtn.disabled = true;
    submitOrderBtn.textContent = "Reserving…";
    orderFeedback.textContent = "";
    orderFeedback.className = "flow-status";

    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_ref: orderRef,
          channel: channel,
          quantity: quantity
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "Failed to create order.");
      }

      // Success feedback
      orderFeedback.textContent = `Order ${data.order.order_ref} (${data.order.quantity} units via ${data.order.channel}) created and added to queue!`;
      orderFeedback.className = "flow-status is-success";

      // Clear inputs
      orderRefInput.value = "";
      qtyInput.value = "";

      // Remove "no orders" placeholder if present
      const emptyRow = document.getElementById("no-orders-row");
      if (emptyRow) {
        emptyRow.remove();
      }

      // Create new row in the Outbound Orders table
      const tr = document.createElement("tr");
      if (!data.order.approved) {
        tr.classList.add("is-breach");
      }

      const shippingCostStr = "R\u00A0" + Number(data.order.shipping_cost).toLocaleString("en-ZA", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });

      tr.innerHTML = `
        <td>${data.order.order_ref}</td>
        <td>${data.order.channel}</td>
        <td class="num">${data.order.quantity}</td>
        <td class="num">${data.order.cartons}</td>
        <td class="num">${Number(data.order.billable_kg).toFixed(2)} kg</td>
        <td class="num">${shippingCostStr}</td>
        <td>
          <span class="badge ${data.order.approved ? 'badge-ok' : 'badge-breach'}">
            ${data.order.approved ? 'Approved' : 'Buffer breach'}
          </span>
        </td>
      `;

      ordersBody.prepend(tr);

      // Flash animation on the new row
      tr.animate(
        [{ backgroundColor: "#FFF1C2" }, { backgroundColor: "transparent" }],
        { duration: 1500, easing: "ease-out" }
      );

    } catch (error) {
      orderFeedback.textContent = error.message;
      orderFeedback.className = "flow-status is-error";
    } finally {
      submitOrderBtn.disabled = false;
      submitOrderBtn.textContent = "Create order";
    }
  });
}

// 2. Courier Freight & Carton Calculator (Flow 3)
const calcForm = document.getElementById("calc-form");
const calcResults = document.getElementById("calc-results");
const calcBtn = document.getElementById("calc-btn");

if (calcForm) {
  calcForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const calcQtyInput = document.getElementById("calc-qty");
    const quantity = parseInt(calcQtyInput.value, 10);

    if (isNaN(quantity) || quantity <= 0) {
      calcResults.style.display = "block";
      calcResults.innerHTML = `<span style="color: var(--breach-text);">Please enter a whole number of 1 or more units.</span>`;
      return;
    }

    calcBtn.disabled = true;
    calcBtn.textContent = "Calculating…";

    try {
      const response = await fetch("/api/calculate-shipping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity: quantity })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "Calculation failed.");
      }

      const costStr = "R\u00A0" + Number(data.shipping_cost_zar).toLocaleString("en-ZA", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });

      let breakdownHtml = "";
      if (data.breakdown && data.breakdown.length > 0) {
        breakdownHtml = "<ul>" + data.breakdown.map(c => 
          `<li>Carton ${c.carton_number}: ${c.units} game${c.units > 1 ? 's' : ''} (Actual: ${c.actual_gross_weight_kg.toFixed(2)} kg, Billable: ${c.billable_weight_kg.toFixed(2)} kg)</li>`
        ).join("") + "</ul>";
      }

      calcResults.style.display = "block";
      calcResults.innerHTML = `
        <strong>Fulfillment Quote for ${quantity} Units:</strong>
        <div>Master Cartons: <strong>${data.cartons_count} box${data.cartons_count > 1 ? 'es' : ''}</strong> (max 4 games/carton)</div>
        <div>Total Billable Weight: <strong>${data.total_billable_weight.toFixed(2)} kg</strong></div>
        <div>Estimated Courier Guy Road Freight: <strong>${costStr}</strong> (incl. 15% VAT)</div>
        ${breakdownHtml}
      `;

      calcResults.animate(
        [{ backgroundColor: "#FFF1C2" }, { backgroundColor: "var(--concrete)" }],
        { duration: 1000, easing: "ease-out" }
      );

    } catch (error) {
      calcResults.style.display = "block";
      calcResults.innerHTML = `<span style="color: var(--breach-text);">${error.message}</span>`;
    } finally {
      calcBtn.disabled = false;
      calcBtn.textContent = "Calculate shipping";
    }
  });
}
