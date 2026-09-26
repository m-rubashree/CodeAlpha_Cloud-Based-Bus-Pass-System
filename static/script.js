document.addEventListener("DOMContentLoaded", function () {
    // Set the minimum travel date to today.
    const dateInputs = document.querySelectorAll('input[type="date"]');

    const today = new Date();
    const localDate = new Date(
        today.getTime() - today.getTimezoneOffset() * 60000
    ).toISOString().slice(0, 10);

    dateInputs.forEach(function (input) {
        input.min = localDate;
    });

    const travelDate = document.getElementById("travel-date");

    if (travelDate && !travelDate.value) {
        travelDate.value = localDate;
    }

    // Update the selected seat display.
    const seatForm = document.getElementById("seat-form");

    if (seatForm) {
        const selectedSeat = document.getElementById("selected-seat");

        seatForm.querySelectorAll('input[name="seat_number"]').forEach(function (seat) {
            seat.addEventListener("change", function () {
                selectedSeat.textContent = seat.value;
            });
        });
    }
});