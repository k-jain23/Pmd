// JavaScript to toggle the visibility of the form and handle form submission
document.addEventListener('DOMContentLoaded', function () {
    // Get references to the button and form elements
    var showFormButton = document.getElementById('showFormButton');
    var bookingForm = document.getElementById('bookingForm');
    var formOverlay = document.getElementById('formOverlay');
    var closeFormButton = document.getElementById('closeFormButton');

    // Get reference to the submit button
    var submitButton = document.getElementById('submitButton');

    // Add click event listener to the "Click Here" button
    showFormButton.addEventListener('click', function () {
        // Show the form and overlay
        bookingForm.style.display = 'block';
        formOverlay.style.display = 'block';
    });

    // Add click event listener to the close button
    closeFormButton.addEventListener('click', function () {
        // Hide the form and overlay
        bookingForm.style.display = 'none';
        formOverlay.style.display = 'none';
    });

    // Handle form submission when the submit button is clicked
    submitButton.addEventListener('click', function (event) {
        // Prevent the default form submission behavior
        event.preventDefault();

        // Create an object to hold the form data
        var formData = {
            activities: Array.from(document.querySelectorAll('input[name="activities[]"]:checked')).map(function (checkbox) {
                return checkbox.value;
            })
        };

        // Send the selected activities to the server
        fetch('/submit', {
            method: 'POST',
            body: JSON.stringify(formData), // Serialize the selected activities
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(function (response) {
            if (response.ok) {
                // Redirect to the results page (results.html)
                window.location.href = 'results.html'; // Update the URL as needed
            } else {
                // Display the error message from the server
                response.text().then(function (errorMessage) {
                    alert('An error occurred: ' + errorMessage);
                });
            }
        })
        .catch(function (error) {
            console.error('Error:', error);
        });
    });
});

// Get all star rating elements
const starRatings = document.querySelectorAll('.star-rating');

// Loop through each star rating element
starRatings.forEach((rating) => {
    const stars = rating.querySelectorAll('.star');
    const city = rating.getAttribute('data-city');

    // Add click event listeners to stars
    stars.forEach((star, index) => {
        star.addEventListener('click', () => {
            const ratingValue = index + 1;

            // Fill the stars up to the clicked star
            stars.forEach((s, i) => {
                if (i < ratingValue) {
                    s.classList.add('active');
                } else {
                    s.classList.remove('active');
                }
            });

            // You can now use 'city' and 'ratingValue' to store the feedback data
            console.log(`City: ${city}, Rating: ${ratingValue}`);
        });
    });
});
