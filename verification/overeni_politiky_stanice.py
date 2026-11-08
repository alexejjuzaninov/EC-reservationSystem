"""Ověření přepnutí pravidla schvalování pouze vlastníkem."""
from overeni_rezervaci import api, expect, STATION, ILYA, MARK


def main():
    path = f"/stations/{STATION}/booking-approval"
    code, station = api(path, actor=ILYA, body={"required": False}, method="PATCH")
    expect("vlastník vypne schvalování", code, 200)
    expect("odpověď obsahuje nové pravidlo", station["requiresBookingApproval"], False)
    code, _ = api(path, actor=MARK, body={"required": True}, method="PATCH")
    expect("cizí řidič nesmí měnit pravidlo", code, 403)
    code, station = api(path, actor=ILYA, body={"required": True}, method="PATCH")
    expect("vlastník vrátí schvalování", code, 200)
    expect("pravidlo je opět aktivní", station["requiresBookingApproval"], True)
    code, station = api(f"/stations/{STATION}")
    expect("pravidlo je uložené", station["requiresBookingApproval"], True)
    print("TEST OK")


if __name__ == "__main__":
    main()
