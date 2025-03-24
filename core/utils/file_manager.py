from typing import Optional


def file_to_list(
        filename: str
):
    with open(filename, 'r+') as f:
        return list(filter(bool, f.read().splitlines()))


def str_to_file(file_name: str, msg: str, mode: Optional[str] = "a"):
    with open(
            file_name,
            mode
    ) as text_file:
        text_file.write(f"{msg}\n")


def shift_file(file):
    with open(file, 'r+') as f:  # open file in read / write mode
        first_line = f.readline()  # read the first line and throw it out
        data = f.read()  # read the rest
        f.seek(0)  # set the cursor to the top of the file
        f.write(data)  # write the data back
        f.truncate()  # set the file size to the current size
        return first_line.strip()


def remove_duplicate_accounts(accounts_list):
    """
    Удаляет дубликаты аккаунтов из списка
    Дубликаты определяются по email (часть до :)
    """
    unique_accounts = {}
    for account in accounts_list:
        try:
            email = account.split(':')[0]
            if email not in unique_accounts:
                unique_accounts[email] = account
        except:
            # Пропускаем некорректно форматированные строки
            pass

    # Возвращаем список уникальных аккаунтов
    return list(unique_accounts.values())
