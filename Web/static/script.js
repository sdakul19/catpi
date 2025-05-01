document.addEventListener('DOMContentLoaded', () => {
    const amountBar = document.getElementById('amount-bar');
    const autoLabel = document.getElementById('auto-label');
    const feedButton = document.getElementById('feed-button');
    const autoButton = document.getElementById('auto-button');
    const setButton = document.getElementById('set-button');
    const saveButton = document.getElementById('save-button');
    const breakfastSpinner = document.getElementById('breakfast-spinner');
    const lunchSpinner = document.getElementById('lunch-spinner');
    const dinnerSpinner = document.getElementById('dinner-spinner');
    const mainScreen = document.getElementById('main-screen');
    const setTimeScreen = document.getElementById('set-time-screen');

    let remaining = 1.0;
    let autoIsOn = false;

    function updateRemaining(value) {
        remaining = value;
        amountBar.style.height = `${remaining * 100}%`;
    }

    function toggleAutoMode() {
        autoIsOn = !autoIsOn;
        autoLabel.textContent = `AUTO: ${autoIsOn ? 'ON' : 'OFF'}`;
        publishMessage();
    }

    function onFeed() {
        updateRemaining(remaining - 0.1);
        publishMessage();
    }

    function saveTimes() {
        const breakfastTime = breakfastSpinner.value;
        const lunchTime = lunchSpinner.value;
        const dinnerTime = dinnerSpinner.value;
        publishMessage(breakfastTime, lunchTime, dinnerTime);
        mainScreen.classList.add('active');
        setTimeScreen.classList.remove('active');
    }

    function publishMessage(breakfastTime = null, lunchTime = null, dinnerTime = null) {
        const msg = {
            remaining: remaining,
            auto: autoIsOn,
            settings: {
                breakfast: breakfastTime || '8:00 AM',
                lunch: lunchTime || '12:00 PM',
                dinner: dinnerTime || '6:00 PM'
            },
            client: 'catpi_ui'
        };
        console.log('Publishing message:', msg);
        // Here you would typically send the message to your MQTT broker
    }

    feedButton.addEventListener('click', onFeed);
    autoButton.addEventListener('click', toggleAutoMode);
    setButton.addEventListener('click', () => {
        mainScreen.classList.remove('active');
        setTimeScreen.classList.add('active');
    });
    saveButton.addEventListener('click', saveTimes);

    updateRemaining(remaining);
});
