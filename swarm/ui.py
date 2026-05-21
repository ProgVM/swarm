from swarm.utils import Colors

def handle_session_error(error):
    print(f"{Colors.ERR}CRITICAL: Session corrupted: {error}{Colors.RESET}")
    print(f"{Colors.MENU}=== SESSION RECOVERY ==={Colors.RESET}")
    print("1. Create new session (ignore corrupted)")
    print("2. Exit")
    
    choice = input(f"{Colors.MENU}Choice: {Colors.RESET}").strip()
    if choice == '1':
        print(f"{Colors.SYS}Creating new session...{Colors.RESET}")
        return False # Indicator to continue
    else:
        print("Exiting.")
        return True # Indicator to exit
