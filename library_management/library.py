"""
Library Management System.

A small, dependency-free system for running a lending library. It
demonstrates object-oriented design in pure Python:

* ``Book``     - a title in the catalogue and how many copies are free.
* ``Member``   - a library member and the loans they currently hold.
* ``Loan``     - one borrowed copy, its due date and any late fee.
* ``Library``  - the catalogue, the members and every lending rule.

Run this file directly to see a full demonstration::

    python library.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class LibraryError(Exception):
    """Base class for every error raised by this module."""


class ValidationError(LibraryError, ValueError):
    """Raised when input data is invalid (bad ISBN, email, year...)."""


class NotFoundError(LibraryError, KeyError):
    """Raised when a book, member or loan does not exist."""

    def __str__(self) -> str:  # KeyError would otherwise wrap it in quotes
        return str(self.args[0]) if self.args else ""


class DuplicateError(LibraryError):
    """Raised when adding a book or member whose ID is already used."""


class LendingError(LibraryError):
    """Raised when a lending rule is broken (no copies, limit reached...)."""


# --------------------------------------------------------------------------
# Lending rules and validation helpers
# --------------------------------------------------------------------------

LOAN_PERIOD_DAYS = 14
MAX_LOANS_PER_MEMBER = 3
DAILY_LATE_FEE = 0.50

_EMAIL_PATTERN = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def _require_text(value: str, field_name: str) -> str:
    """Return ``value`` stripped, or raise if it is empty or not a string."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _validate_email(email: str) -> str:
    """Return a normalized (lower-case) email, or raise if it is malformed."""
    email = _require_text(email, "Email").lower()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationError(f"Invalid email address: {email!r}.")
    return email


def _validate_positive_int(value: int, field_name: str) -> int:
    """Return ``value`` if it is an int >= 1, otherwise raise."""
    # bool is a subclass of int, but True/False are never valid counts.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{field_name} must be a positive integer.")
    return value


def validate_isbn(isbn: str) -> str:
    """Return a cleaned ISBN-13 (digits only) or raise if it is invalid.

    Hyphens and spaces are allowed in the input. The check digit is
    verified with the standard ISBN-13 weighting (1, 3, 1, 3, ...).
    """
    digits = re.sub(r"[\s-]", "", _require_text(isbn, "ISBN"))
    if not re.fullmatch(r"\d{13}", digits):
        raise ValidationError(f"ISBN must have 13 digits, got {isbn!r}.")
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits))
    if total % 10:
        raise ValidationError(f"ISBN check digit is wrong: {isbn!r}.")
    return digits


def calculate_late_fee(days_late: int) -> float:
    """Fee owed for returning a book ``days_late`` days after it was due."""
    return round(max(days_late, 0) * DAILY_LATE_FEE, 2)


# --------------------------------------------------------------------------
# Domain classes
# --------------------------------------------------------------------------

@dataclass
class Book:
    """A title in the catalogue.

    Responsibility (SRP): describe one title and track how many of its
    copies are on the shelf. It does not know who borrowed them.
    """

    isbn: str
    title: str
    author: str
    year: int
    total_copies: int = 1
    _available: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.isbn = validate_isbn(self.isbn)
        self.title = _require_text(self.title, "Title")
        self.author = _require_text(self.author, "Author")
        if (isinstance(self.year, bool) or not isinstance(self.year, int)
                or not 1450 <= self.year <= date.today().year):
            raise ValidationError(
                f"Year must be between 1450 and {date.today().year}.")
        self.total_copies = _validate_positive_int(self.total_copies,
                                                   "Total copies")
        self._available = self.total_copies

    @property
    def available_copies(self) -> int:
        """Copies currently on the shelf (read-only)."""
        return self._available

    @property
    def is_available(self) -> bool:
        return self._available > 0

    def check_out(self) -> None:
        """Take one copy off the shelf."""
        if not self.is_available:
            raise LendingError(f"No copies of {self.title!r} are available.")
        self._available -= 1

    def check_in(self) -> None:
        """Put one copy back on the shelf."""
        if self._available >= self.total_copies:
            raise LendingError(f"All copies of {self.title!r} are in.")
        self._available += 1

    def add_copies(self, count: int) -> None:
        """Add new copies of this title to the collection."""
        count = _validate_positive_int(count, "Count")
        self.total_copies += count
        self._available += count

    def __str__(self) -> str:
        return (f"{self.title} by {self.author} ({self.year}) "
                f"[{self._available}/{self.total_copies} available]")


@dataclass
class Loan:
    """One borrowed copy of a book."""

    loan_id: int
    isbn: str
    member_id: str
    borrowed_on: date
    due_on: date
    returned_on: Optional[date] = None
    fee: float = 0.0

    @property
    def is_active(self) -> bool:
        return self.returned_on is None

    def days_overdue(self, today: date) -> int:
        """Days past the due date (0 if not late)."""
        end = self.returned_on or today
        return max((end - self.due_on).days, 0)

    def close(self, returned_on: date) -> float:
        """Mark the loan as returned and return the late fee owed."""
        if not self.is_active:
            raise LendingError(f"Loan #{self.loan_id} is already closed.")
        if returned_on < self.borrowed_on:
            raise ValidationError("Return date is before the borrow date.")
        self.returned_on = returned_on
        self.fee = calculate_late_fee(self.days_overdue(returned_on))
        return self.fee


@dataclass
class Member:
    """A library member.

    Responsibility (SRP): hold one member's profile, their active loans
    and the fees they owe.
    """

    member_id: str
    name: str
    email: str
    joined_on: date = field(default_factory=date.today)
    _active_loans: List[Loan] = field(default_factory=list, init=False,
                                      repr=False)
    _fees_owed: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.member_id = _require_text(self.member_id, "Member ID")
        self.name = _require_text(self.name, "Name")
        self.email = _validate_email(self.email)

    @property
    def active_loans(self) -> List[Loan]:
        """A copy of the member's open loans."""
        return list(self._active_loans)

    @property
    def fees_owed(self) -> float:
        return self._fees_owed

    @property
    def can_borrow(self) -> bool:
        """Members may borrow while under the loan limit and owing nothing."""
        return (len(self._active_loans) < MAX_LOANS_PER_MEMBER
                and self._fees_owed == 0)

    def start_loan(self, loan: Loan) -> None:
        self._active_loans.append(loan)

    def end_loan(self, loan: Loan) -> None:
        self._active_loans.remove(loan)
        self._fees_owed = round(self._fees_owed + loan.fee, 2)

    def pay_fees(self, amount: float) -> float:
        """Pay toward outstanding fees and return what is still owed."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValidationError("Amount must be a number.")
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        if amount > self._fees_owed:
            raise ValidationError(
                f"Amount {amount:.2f} exceeds fees owed "
                f"({self._fees_owed:.2f}).")
        self._fees_owed = round(self._fees_owed - amount, 2)
        return self._fees_owed

    def __str__(self) -> str:
        return (f"[{self.member_id}] {self.name:<14} "
                f"loans {len(self._active_loans)}  "
                f"fees ${self._fees_owed:.2f}")


class Library:
    """The catalogue, the members and the lending rules that connect them.

    Responsibility (SRP): coordinate books, members and loans. Rules that
    belong to one object (copy counts, fees owed) stay in that object.

    ``clock`` is injected (Dependency Inversion) so the current date can
    be controlled in demos and tests instead of always being today.
    """

    def __init__(self, clock: Callable[[], date] = date.today) -> None:
        self._clock = clock
        self._books: Dict[str, Book] = {}
        self._members: Dict[str, Member] = {}
        self._loans: List[Loan] = []

    # ----- books ----------------------------------------------------------

    def add_book(self, isbn: str, title: str, author: str, year: int,
                 copies: int = 1) -> Book:
        """Add a new title, or raise ``DuplicateError`` if the ISBN exists."""
        book = Book(isbn, title, author, year, copies)
        if book.isbn in self._books:
            raise DuplicateError(f"ISBN {book.isbn} is already in the "
                                 f"catalogue; use add_copies instead.")
        self._books[book.isbn] = book
        return book

    def get_book(self, isbn: str) -> Book:
        """Return the book with ``isbn`` or raise ``NotFoundError``."""
        try:
            return self._books[validate_isbn(isbn)]
        except KeyError:
            raise NotFoundError(f"No book with ISBN {isbn!r}.") from None

    def add_copies(self, isbn: str, count: int) -> Book:
        book = self.get_book(isbn)
        book.add_copies(count)
        return book

    def remove_book(self, isbn: str) -> Book:
        """Remove a title. Refused while any copy is on loan."""
        book = self.get_book(isbn)
        if book.available_copies < book.total_copies:
            raise LendingError(
                f"Cannot remove {book.title!r}: copies are on loan.")
        del self._books[book.isbn]
        return book

    def search(self, query: str) -> List[Book]:
        """Books whose title or author contains ``query`` (any case)."""
        query = _require_text(query, "Search query").lower()
        return [b for b in self.list_books()
                if query in b.title.lower() or query in b.author.lower()]

    def list_books(self) -> List[Book]:
        """All books sorted by title."""
        return sorted(self._books.values(), key=lambda b: b.title)

    # ----- members --------------------------------------------------------

    def add_member(self, member_id: str, name: str, email: str) -> Member:
        """Register a new member; IDs and emails must be unique."""
        member = Member(member_id, name, email, self._clock())
        if member.member_id in self._members:
            raise DuplicateError(
                f"Member ID {member.member_id!r} already exists.")
        if any(m.email == member.email for m in self._members.values()):
            raise DuplicateError(
                f"Email {member.email!r} is already registered.")
        self._members[member.member_id] = member
        return member

    def get_member(self, member_id: str) -> Member:
        try:
            return self._members[member_id]
        except KeyError:
            raise NotFoundError(f"No member with ID {member_id!r}.") from None

    def remove_member(self, member_id: str) -> Member:
        """Remove a member. Refused while they hold books or owe fees."""
        member = self.get_member(member_id)
        if member.active_loans or member.fees_owed:
            raise LendingError(f"{member.name} still has loans or fees.")
        del self._members[member_id]
        return member

    # ----- lending --------------------------------------------------------

    def borrow_book(self, member_id: str, isbn: str) -> Loan:
        """Lend one copy of a book to a member for ``LOAN_PERIOD_DAYS``."""
        member = self.get_member(member_id)
        book = self.get_book(isbn)
        if member.fees_owed:
            raise LendingError(f"{member.name} owes "
                               f"${member.fees_owed:.2f} in late fees.")
        if not member.can_borrow:
            raise LendingError(f"{member.name} has reached the limit of "
                               f"{MAX_LOANS_PER_MEMBER} loans.")
        if any(loan.isbn == book.isbn for loan in member.active_loans):
            raise LendingError(f"{member.name} already has {book.title!r}.")

        book.check_out()
        today = self._clock()
        loan = Loan(len(self._loans) + 1, book.isbn, member.member_id,
                    today, today + timedelta(days=LOAN_PERIOD_DAYS))
        member.start_loan(loan)
        self._loans.append(loan)
        return loan

    def return_book(self, member_id: str, isbn: str) -> Loan:
        """Return a borrowed book; any late fee is added to the member."""
        member = self.get_member(member_id)
        book = self.get_book(isbn)
        loan = next((ln for ln in member.active_loans if ln.isbn == book.isbn),
                    None)
        if loan is None:
            raise NotFoundError(
                f"{member.name} has not borrowed {book.title!r}.")
        loan.close(self._clock())
        book.check_in()
        member.end_loan(loan)
        return loan

    def overdue_loans(self) -> List[Loan]:
        """Active loans past their due date, most overdue first."""
        today = self._clock()
        late = [ln for ln in self._loans
                if ln.is_active and ln.days_overdue(today) > 0]
        return sorted(late, key=lambda ln: ln.days_overdue(today),
                      reverse=True)

    # ----- reports --------------------------------------------------------

    def most_borrowed(self, n: int = 3) -> List[tuple]:
        """The ``n`` most borrowed titles as ``(book, times_borrowed)``."""
        n = _validate_positive_int(n, "n")
        counts: Dict[str, int] = {}
        for loan in self._loans:
            counts[loan.isbn] = counts.get(loan.isbn, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(self._books[isbn], times) for isbn, times in ranked[:n]
                if isbn in self._books]

    def get_statistics(self) -> Dict[str, object]:
        """Library-wide statistics as a dictionary."""
        total = sum(b.total_copies for b in self._books.values())
        available = sum(b.available_copies for b in self._books.values())
        active = [ln for ln in self._loans if ln.is_active]
        return {
            "titles": len(self._books),
            "total_copies": total,
            "copies_on_loan": total - available,
            "members": len(self._members),
            "active_loans": len(active),
            "overdue_loans": len(self.overdue_loans()),
            "loans_all_time": len(self._loans),
            "late_fees_charged": round(
                sum(ln.fee for ln in self._loans), 2),
            "fees_outstanding": round(
                sum(m.fees_owed for m in self._members.values()), 2),
        }

    def display_catalogue(self) -> None:
        """Print every book as a formatted table."""
        if not self._books:
            print("The catalogue is empty.")
            return
        print(f"{'ISBN':<14} {'Title':<28} {'Author':<20} {'Avail':>7}")
        print("-" * 72)
        for b in self.list_books():
            print(f"{b.isbn:<14} {b.title:<28} {b.author:<20} "
                  f"{b.available_copies:>3}/{b.total_copies:<3}")


# --------------------------------------------------------------------------
# Demonstration
# --------------------------------------------------------------------------

class _DemoClock:
    """A controllable clock so the demo output is always the same."""

    def __init__(self, start: date) -> None:
        self.today = start

    def __call__(self) -> date:
        return self.today

    def advance(self, days: int) -> None:
        self.today += timedelta(days=days)


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> None:
    """Walk through every feature of the system."""
    clock = _DemoClock(date(2024, 8, 1))
    library = Library(clock)

    _section("1. Building the catalogue")
    library.add_book("978-0-13-235088-4", "Clean Code", "Robert C. Martin",
                     2008, copies=2)
    library.add_book("978-0-201-63361-0", "Design Patterns", "Erich Gamma",
                     1994)
    library.add_book("978-1-4919-4600-8", "Fluent Python", "Luciano Ramalho",
                     2015, copies=2)
    library.add_book("978-0-13-595705-9", "The Pragmatic Programmer",
                     "David Thomas", 2019)
    library.add_copies("978-0-201-63361-0", 1)
    library.display_catalogue()

    _section("2. Registering members")
    library.add_member("M001", "Ahmed Hassan", "ahmed@example.com")
    library.add_member("M002", "Sara Ali", "sara@example.com")
    library.add_member("M003", "Omar Khaled", "omar@example.com")
    for member_id in ("M001", "M002", "M003"):
        print(f"  {library.get_member(member_id)}")

    _section("3. Borrowing books (2024-08-01)")
    for member_id, isbn in [("M001", "9780132350884"),
                            ("M001", "9781491946008"),
                            ("M002", "9780132350884"),
                            ("M002", "9780201633610"),
                            ("M003", "9781491946008")]:
        loan = library.borrow_book(member_id, isbn)
        book = library.get_book(isbn)
        print(f"  Loan #{loan.loan_id}: {member_id} took {book.title!r}, "
              f"due {loan.due_on}")

    _section("4. Searching")
    for query in ("python", "martin"):
        titles = [b.title for b in library.search(query)]
        print(f"  {query!r:<10} -> {titles}")

    _section("5. Returns (one on time, one late)")
    clock.advance(10)   # 2024-08-11
    loan = library.return_book("M002", "9780132350884")
    print(f"  {clock.today}: M002 returned Clean Code, fee ${loan.fee:.2f}")
    clock.advance(9)    # 2024-08-20, five days after the due date
    loan = library.return_book("M001", "9780132350884")
    print(f"  {clock.today}: M001 returned Clean Code, "
          f"{loan.days_overdue(clock.today)} days late, fee ${loan.fee:.2f}")

    _section("6. Overdue loans (2024-08-20)")
    for loan in library.overdue_loans():
        book = library.get_book(loan.isbn)
        print(f"  #{loan.loan_id} {loan.member_id} {book.title!r}: "
              f"{loan.days_overdue(clock.today)} days overdue")

    _section("7. Fees block borrowing until paid")
    try:
        library.borrow_book("M001", "9780135957059")
    except LendingError as error:
        print(f"  Refused: {error}")
    left = library.get_member("M001").pay_fees(2.50)
    print(f"  M001 paid $2.50, still owes ${left:.2f}")
    loan = library.borrow_book("M001", "9780135957059")
    print(f"  Loan #{loan.loan_id}: M001 took 'The Pragmatic Programmer'")

    _section("8. Most borrowed and statistics")
    for book, times in library.most_borrowed(3):
        print(f"  {times}x {book.title}")
    print()
    for key, value in library.get_statistics().items():
        print(f"  {key:<24}: {value}")

    _section("9. Error handling")
    bad_calls = [
        ("Bad ISBN check digit",
         lambda: library.add_book("978-0-13-235088-5", "X", "Y", 2000)),
        ("Duplicate ISBN",
         lambda: library.add_book("9780132350884", "Copy", "Y", 2000)),
        ("Invalid email",
         lambda: library.add_member("M009", "Test", "not-an-email")),
        ("Unknown member",
         lambda: library.borrow_book("M999", "9780132350884")),
        ("Book not borrowed",
         lambda: library.return_book("M003", "9780132350884")),
        ("Remove book on loan",
         lambda: library.remove_book("9781491946008")),
        ("Overpay fees",
         lambda: library.get_member("M003").pay_fees(5)),
    ]
    for label, call in bad_calls:
        try:
            call()
        except LibraryError as error:
            print(f"  {label:<22} -> {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
