from swarm.utils import Colors

def handle_session_error(error):
    print(f"{Colors.ERR}CRITICAL: Сессия повреждена: {error}{Colors.RESET}")
    print(f"{Colors.MENU}=== ВОССТАНОВЛЕНИЕ СЕССИИ ==={Colors.RESET}")
    print("1. Создать новую сессию (игнорировать поврежденную)")
    print("2. Завершить работу")
    
    choice = input(f"{Colors.MENU}Выбор: {Colors.RESET}").strip()
    if choice == '1':
        print(f"{Colors.SYS}Создание новой сессии...{Colors.RESET}")
        return False # Indicator to continue
    else:
        print("Завершение работы.")
        return True # Indicator to exit
