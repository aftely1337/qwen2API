from typing import Iterable, Any


def count_healthy_accounts(accounts: Iterable[Any]) -> int:
    total = 0
    for account in accounts:
        status = account.get_status_code() if hasattr(account, "get_status_code") else getattr(account, "status_code", "")
        if status == "valid" and not account.is_rate_limited():
            total += 1
    return total
