document.addEventListener("DOMContentLoaded", function () {

    // Set today's date automatically
    const dateInput =
        document.getElementById("attendanceDate");

    if (dateInput && !dateInput.value) {

        const today = new Date();

        const year = today.getFullYear();

        const month =
            String(today.getMonth() + 1)
            .padStart(2, "0");

        const day =
            String(today.getDate())
            .padStart(2, "0");

        dateInput.value =
            `${year}-${month}-${day}`;
    }


    // Automatically hide flash messages
    setTimeout(function () {

        const messages =
            document.querySelectorAll(".flash");

        messages.forEach(function (message) {

            message.style.transition =
                "opacity 0.5s";

            message.style.opacity = "0";

        });

    }, 4000);

});