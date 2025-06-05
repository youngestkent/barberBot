# Telegram Barber Shop Booking Bot

This is a Telegram bot for a barber shop that allows clients to book appointments and administrators to manage working days and view bookings.

## Features

- Client appointment booking with service selection
- Admin management of working days
- Admin view of all bookings
- Contact information collection from clients
- Automatic database storage of client information and appointments
- Marking appointments as completed

## Services Offered

- Men's Haircut (Мужская стрижка)
- Women's Haircut (Женская стрижка)
- Children's Haircut (Детская стрижка)
- Hair Coloring (Окрашивание)

## Setup Instructions

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Edit the `bot.py` file to set your Telegram Bot Token:
   - Replace `YOUR_BOT_TOKEN` with your actual bot token from BotFather
   - Replace `+1234567890` in the `ADMIN_PHONE` variable with the actual admin phone number

3. Run the bot:
   ```
   python bot.py
   ```

## Admin Features

When an admin logs in (identified by their phone number), they can:
- View all current bookings
- Add new working days
- Remove existing working days
- Mark appointments as completed

## Client Features

Clients can:
- Select a service type
- Choose an available date from admin-defined working days
- Select an available time slot
- Confirm their booking

## Database

The bot uses SQLite to store:
- Client information (name, phone number)
- Appointment details (service, date, time)
- Working days

The database file `barber_shop.db` is created automatically when the bot is first run.

## Usage

1. Start the bot with the `/start` command
2. Share your phone number when prompted
3. Follow the on-screen instructions to book an appointment or access admin features