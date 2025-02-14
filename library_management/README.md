# Library Management System

A clean, object-oriented library management system written in **pure
Python** (standard library only). It manages a catalogue of books with
multiple copies, registers members, lends and returns books with due dates,
charges late fees, and produces reports such as overdue loans, most borrowed
titles and library-wide statistics, with input validation and clear error
handling throughout.

## Features

- **Catalogue**: books with ISBN-13 (check digit verified), title, author,
  year and number of copies.
- **Members**: unique member IDs and emails, validated on registration.
- **Lending rules**: 14-day loans, at most 3 books per member, no borrowing
  the same title twice, and no borrowing while late fees are unpaid.
- **Late fees**: 0.50 per day late, added to the member's balance on return.
- **Search**: by title or author, case-insensitive.
- **Reports**: overdue loans, most borrowed titles and library statistics.
- **Safe removal**: books on loan and members with loans or fees cannot be
  removed.
- **Validation and errors**: a custom exception hierarchy for invalid data,
  duplicates, unknown records and broken lending rules.
- **Zero dependencies**: runs anywhere Python 3.8+ is installed.

## Project structure

```
library_management/
├── library.py         # Classes and a runnable demonstration
├── README.md          # This file
└── requirements.txt   # No external dependencies
```

## Installation

```bash
git clone https://github.com/khaledkamel1818/library-management-system.git
cd library-management-system/library_management
python library.py
```

No `pip install` is needed.

## Usage

```python
from library import Library, LibraryError

library = Library()

# Catalogue and members
library.add_book("978-0-13-235088-4", "Clean Code", "Robert C. Martin",
                 2008, copies=2)
library.add_member("M001", "Ahmed Hassan", "ahmed@example.com")

# Lending
loan = library.borrow_book("M001", "9780132350884")
print(loan.due_on)                       # today + 14 days
print(library.get_book("9780132350884")) # Clean Code ... [1/2 available]

loan = library.return_book("M001", "9780132350884")
print(loan.fee)                          # 0.0 when returned on time

# Reports
print(library.search("clean"))
print(library.overdue_loans())
print(library.most_borrowed(3))
print(library.get_statistics())
library.display_catalogue()

# Errors are explicit and catchable
try:
    library.borrow_book("M999", "9780132350884")
except LibraryError as error:
    print(error)   # No member with ID 'M999'.
```

`Library` takes an optional `clock` (any function returning a `date`), so
dates can be controlled in tests and demos:

```python
from datetime import date
library = Library(clock=lambda: date(2024, 8, 1))
```

## Classes and methods

### `Book`

| Member | Description |
|---|---|
| `Book(isbn, title, author, year, total_copies=1)` | Creates a validated book. |
| `available_copies`, `is_available` | Copies on the shelf (read-only). |
| `check_out()`, `check_in()` | Take a copy off or put it back on the shelf. |
| `add_copies(count)` | Add more copies of the title. |

### `Loan`

| Member | Description |
|---|---|
| `loan_id`, `isbn`, `member_id`, `borrowed_on`, `due_on` | Loan details. |
| `is_active` | `True` until the book is returned. |
| `days_overdue(today)` | Days past the due date. |
| `close(returned_on)` | Ends the loan and returns the late fee. |

### `Member`

| Member | Description |
|---|---|
| `Member(member_id, name, email, joined_on=today)` | Creates a validated member. |
| `active_loans`, `fees_owed` | Read-only views of the member's state. |
| `can_borrow` | Under the loan limit and owing nothing. |
| `pay_fees(amount)` | Pays toward late fees and returns what is still owed. |

### `Library`

| Method | Description |
|---|---|
| `add_book(isbn, title, author, year, copies=1)` | Adds a title; rejects duplicate ISBNs. |
| `get_book(isbn)` / `remove_book(isbn)` | Look up or remove a title. |
| `add_copies(isbn, count)` | Adds copies to an existing title. |
| `search(query)` | Books whose title or author contains `query`. |
| `list_books()` | All books sorted by title. |
| `add_member(member_id, name, email)` | Registers a member; rejects duplicate IDs and emails. |
| `get_member(member_id)` / `remove_member(member_id)` | Look up or remove a member. |
| `borrow_book(member_id, isbn)` | Lends a copy and returns the `Loan`. |
| `return_book(member_id, isbn)` | Returns a copy and charges any late fee. |
| `overdue_loans()` | Active loans past their due date. |
| `most_borrowed(n=3)` | The most borrowed titles. |
| `get_statistics()` | A dictionary of library-wide statistics. |
| `display_catalogue()` | Prints a formatted table. |

### Exceptions

```
LibraryError
├── ValidationError   # bad ISBN, email, year, amount or argument
├── NotFoundError     # unknown book, member or loan
├── DuplicateError    # ISBN, member ID or email already used
└── LendingError      # no copies left, loan limit, unpaid fees...
```

## OOP concepts used

- **Encapsulation**: copy counts, active loans and fees are private and only
  change through methods that enforce the rules (`check_out`, `end_loan`,
  `pay_fees`).
- **Abstraction**: callers just call `borrow_book()`; the checks on copies,
  limits, duplicates and fees stay hidden inside.
- **Composition**: a `Library` *has* books, members and loans; a `Member`
  *has* loans.
- **Inheritance**: every exception derives from `LibraryError`, so callers
  can catch one type or all of them.
- **Properties**: `available_copies`, `is_available` and `can_borrow` are
  computed, read-only attributes.
- **Dunder methods**: `__str__` gives books and members a readable form.

### SOLID principles

- **Single Responsibility**: `Book` tracks copies, `Member` tracks loans and
  fees, `Loan` tracks dates and the fee, `Library` coordinates them.
- **Open/Closed**: lending rules are module constants and the fee formula
  lives in `calculate_late_fee`, so policies change in one place.
- **Liskov Substitution**: each custom exception works wherever its base
  (`LibraryError`, `ValueError` or `KeyError`) is expected.
- **Interface Segregation**: each class exposes a small, focused set of
  methods.
- **Dependency Inversion**: `Library` depends on an injected `clock`
  function rather than calling `date.today()` directly, which makes the
  date-based rules easy to test.

## Expected output

Running `python library.py` prints:

```
========================================================================
1. Building the catalogue
========================================================================
ISBN           Title                        Author                 Avail
------------------------------------------------------------------------
9780132350884  Clean Code                   Robert C. Martin       2/2
9780201633610  Design Patterns              Erich Gamma            2/2
9781491946008  Fluent Python                Luciano Ramalho        2/2
9780135957059  The Pragmatic Programmer     David Thomas           1/1

========================================================================
2. Registering members
========================================================================
  [M001] Ahmed Hassan   loans 0  fees $0.00
  [M002] Sara Ali       loans 0  fees $0.00
  [M003] Omar Khaled    loans 0  fees $0.00

========================================================================
3. Borrowing books (2024-08-01)
========================================================================
  Loan #1: M001 took 'Clean Code', due 2024-08-15
  Loan #2: M001 took 'Fluent Python', due 2024-08-15
  Loan #3: M002 took 'Clean Code', due 2024-08-15
  Loan #4: M002 took 'Design Patterns', due 2024-08-15
  Loan #5: M003 took 'Fluent Python', due 2024-08-15

========================================================================
4. Searching
========================================================================
  'python'   -> ['Fluent Python']
  'martin'   -> ['Clean Code']

========================================================================
5. Returns (one on time, one late)
========================================================================
  2024-08-11: M002 returned Clean Code, fee $0.00
  2024-08-20: M001 returned Clean Code, 5 days late, fee $2.50

========================================================================
6. Overdue loans (2024-08-20)
========================================================================
  #2 M001 'Fluent Python': 5 days overdue
  #4 M002 'Design Patterns': 5 days overdue
  #5 M003 'Fluent Python': 5 days overdue

========================================================================
7. Fees block borrowing until paid
========================================================================
  Refused: Ahmed Hassan owes $2.50 in late fees.
  M001 paid $2.50, still owes $0.00
  Loan #6: M001 took 'The Pragmatic Programmer'

========================================================================
8. Most borrowed and statistics
========================================================================
  2x Clean Code
  2x Fluent Python
  1x The Pragmatic Programmer

  titles                  : 4
  total_copies            : 7
  copies_on_loan          : 4
  members                 : 3
  active_loans            : 4
  overdue_loans           : 3
  loans_all_time          : 6
  late_fees_charged       : 2.5
  fees_outstanding        : 0.0

========================================================================
9. Error handling
========================================================================
  Bad ISBN check digit   -> ValidationError: ISBN check digit is wrong: '978-0-13-235088-5'.
  Duplicate ISBN         -> DuplicateError: ISBN 9780132350884 is already in the catalogue; use add_copies instead.
  Invalid email          -> ValidationError: Invalid email address: 'not-an-email'.
  Unknown member         -> NotFoundError: No member with ID 'M999'.
  Book not borrowed      -> NotFoundError: Omar Khaled has not borrowed 'Clean Code'.
  Remove book on loan    -> LendingError: Cannot remove 'Fluent Python': copies are on loan.
  Overpay fees           -> ValidationError: Amount 5.00 exceeds fees owed (0.00).
```

## Author

**Khaled Kamel** · [GitHub](https://github.com/khaledkamel1818)
