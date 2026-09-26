// Refresh only the slot grid so availability stays current without reloading the page.
const slotGrid = document.querySelector("#slot-grid");

if (slotGrid) {
  const refreshSlots = async () => {
    try {
      const response = await fetch(slotGrid.dataset.slotsUrl);
      if (!response.ok) return;
      const slots = await response.json();
      let freeCount = 0;

      for (const slot of slots) {
        const tile = slotGrid.querySelector(`[data-slot="${slot.slot_number}"]`);
        if (!tile) continue;
        const isFree = slot.status === "Free";
        tile.classList.toggle("is-free", isFree);
        tile.classList.toggle("is-occupied", !isFree);
        tile.querySelector(".slot-status").textContent = slot.status;
        if (isFree) freeCount += 1;
      }
      document.querySelector("#available-count").textContent = freeCount;
    } catch (error) {
      // Keep the last displayed state if a brief network error interrupts polling.
    }
  };

  window.setInterval(refreshSlots, 5000);
}