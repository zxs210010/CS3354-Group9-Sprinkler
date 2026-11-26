def set_notification_time():
    print("Set Notification Time")

    while True:
        notification_time = input("Enter notification time (HH:MM): ")

        try:
            hour, minute = map(int, notification_time.split(":"))

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                print(f"Notification time set to {hour:02d}:{minute:02d}")
                return notification_time
            else:
                print("Invalid time. Please enter a valid time.")

        except ValueError:
            print("Invalid format. Please use HH:MM.")


# Test case: Set Notification Time
set_notification_time()