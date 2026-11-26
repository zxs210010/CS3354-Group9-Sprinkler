from datetime import datetime


notification_enabled = False
notification_time = None


def set_notification_time():
    global notification_time

    while True:
        time_input = input("Enter notification time (HH:MM): ")

        try:
            datetime.strptime(time_input, "%H:%M")
            notification_time = time_input
            print("Notification time changed to:", notification_time)
            break
        except ValueError:
            print("Invalid time. Please use HH:MM.")


def enable_notifications():
    global notification_enabled

    if notification_time is None:
        print("Please set a notification time first.")
    else:
        notification_enabled = True
        print("Notifications enabled.")


def disable_notifications():
    global notification_enabled

    notification_enabled = False
    print("Notifications disabled.")


def show_settings():
    print("\nCurrent Notification Settings")

    if notification_time is None:
        print("Notification time: Not set")
    else:
        print("Notification time:", notification_time)

    if notification_enabled:
        print("Notifications: Enabled")
    else:
        print("Notifications: Disabled")


def main():
    while True:
        print("\n--- Notification Settings ---")
        print("1. Set/change notification time")
        print("2. Enable notifications")
        print("3. Disable notifications")
        print("4. Show notification settings")
        print("5. Exit")

        choice = input("Select an option: ")

        if choice == "1":
            set_notification_time()

        elif choice == "2":
            enable_notifications()

        elif choice == "3":
            disable_notifications()

        elif choice == "4":
            show_settings()

        elif choice == "5":
            print("Exiting notification settings.")
            break

        else:
            print("Invalid option. Please choose 1-5.")


main()