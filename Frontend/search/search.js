let currentFocus = -1;

// Function to fetch autocomplete suggestions
async function autocompleteSuggestions(query) {
    try {
        const response = await fetch(`http://127.0.0.1:8000/batch-encoder/autocomplete/?query=${encodeURIComponent(query)}`);
        if (response.ok) {
            const data = await response.json();
            return data.suggestions;
        }
    } catch (error) {
        console.error('Error fetching autocomplete suggestions:', error);
    }
    return [];
}

// Function to display autocomplete suggestions
function showAutocompleteSuggestions(suggestions, autocompleteResults, searchInput) {
    autocompleteResults.innerHTML = ''; // Clear previous

    suggestions.forEach(suggestion => {
        const div = document.createElement('div');
        div.textContent = suggestion;
        div.addEventListener('click', () => {
            searchInput.value = suggestion;
            autocompleteResults.innerHTML = '';
            search(suggestion);
        });
        autocompleteResults.appendChild(div);
    });
}

// Function to add active class to current suggestion
function addActive(suggestions) {
    if (!suggestions) return;
    removeActive(suggestions);

    if (currentFocus >= suggestions.length) currentFocus = 0;
    if (currentFocus < 0) currentFocus = suggestions.length - 1;

    suggestions[currentFocus].classList.add('autocomplete-active');
    suggestions[currentFocus].scrollIntoView({
        block: 'nearest',
        behavior: 'smooth'
    });
}

// Function to remove active class
function removeActive(suggestions) {
    for (let i = 0; i < suggestions.length; i++) {
        suggestions[i].classList.remove('autocomplete-active');
    }
}

// Function to perform search request
async function search(identifier) {
    try {
        const response = await fetch(`http://127.0.0.1:8000/batch-encoder/search/?identifier=${encodeURIComponent(identifier)}`);
        if (response.ok) {
            const data = await response.json();
            displaySearchresults(data);
        } else {
            alert('Search failed. Electrode not found.');
        }
    } catch (error) {
        console.error('Error performing search:', error);
        alert('An error occurred while performing the search.');
    }
}

// Function to store results and redirect
function displaySearchresults(data) {
    try {
        localStorage.setItem('searchResults', JSON.stringify(data));
        window.location.href = 'http://127.0.0.1:8080/search/searchResults_2.html';
    } catch (error) {
        console.error('Error storing search results:', error);
        alert('Failed to save search results. Please try again.');
    }
}

// DOMContentLoaded handler to safely attach event listeners
window.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searcH');
    const autocompleteResults = document.getElementById('autocomplete-results');
    const searchBox = document.getElementById('searchBox');

    if (searchInput && autocompleteResults && searchBox) {
        // Input listener
        searchInput.addEventListener('input', async () => {
            const query = searchInput.value;
            if (query.length >= 3) {
                const suggestions = await autocompleteSuggestions(query);
                showAutocompleteSuggestions(suggestions, autocompleteResults, searchInput);
            } else {
                autocompleteResults.innerHTML = '';
            }
        });

        // Keyboard nav listener
        searchInput.addEventListener('keydown', function (e) {
            const suggestions = autocompleteResults.getElementsByTagName('div');

            if (e.key === 'ArrowDown') {
                currentFocus++;
                addActive(suggestions);
            } else if (e.key === 'ArrowUp') {
                currentFocus--;
                addActive(suggestions);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (currentFocus > -1 && suggestions[currentFocus]) {
                    suggestions[currentFocus].click();
                } else {
                    search(searchInput.value);
                }
            }
        });

        // Click-outside listener
        document.addEventListener('click', function (event) {
            const isClickInsideSearchBox = searchBox.contains(event.target);
            const isClickInsideResults = autocompleteResults.contains(event.target);
            if (!isClickInsideSearchBox && !isClickInsideResults) {
                autocompleteResults.innerHTML = '';
            }
        });
    } else {
        console.warn("Search bar not found in DOM. Skipping autocomplete setup.");
    }
});
