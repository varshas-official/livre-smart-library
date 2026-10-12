"""Seed 30 identifiable academic books. Inventory counts are sample data."""
BOOKS = [
("Object-Oriented Analysis and Design","Ali Bahrami","Object-Oriented Analysis and Design","","",""),
("Object-Oriented Analysis and Design with Applications","Grady Booch, Robert A. Maksimchuk, Michael W. Engle, Bobbi J. Young, Jim Conallen, Kelli A. Houston","OO Analysis and Design","3rd edition","Addison-Wesley","9780201895513"),
("Applying UML and Patterns","Craig Larman","UML and Modelling","3rd edition","Prentice Hall","9780131489066"),
("UML Distilled","Martin Fowler","UML and Modelling","3rd edition","Addison-Wesley",""),
("Design Patterns: Elements of Reusable Object-Oriented Software","Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides","Design Patterns","","Addison-Wesley",""),
("Software Engineering","Ian Sommerville","Software Engineering","10th edition","Pearson",""),
("Software Engineering: A Practitioner's Approach","Roger S. Pressman, Bruce R. Maxim","Software Engineering","9th edition","McGraw-Hill",""),
("Clean Code","Robert C. Martin","Software Engineering","","Prentice Hall",""),
("Head First Design Patterns","Eric Freeman, Elisabeth Robson","Design Patterns","2nd edition","O'Reilly Media",""),
("The Pragmatic Programmer","David Thomas, Andrew Hunt","Software Engineering","20th Anniversary edition","Addison-Wesley",""),
("Fundamentals of Software Architecture","Mark Richards, Neal Ford","Software Architecture","","O'Reilly Media",""),
("Effective Java","Joshua Bloch","Java and OOP","3rd edition","Addison-Wesley",""),
("Introduction to Algorithms","Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein","Data Structures and Algorithms","4th edition","MIT Press",""),
("Operating System Concepts","Abraham Silberschatz, Peter B. Galvin, Greg Gagne","Operating Systems","10th edition","Wiley",""),
("Database System Concepts","Abraham Silberschatz, Henry F. Korth, S. Sudarshan","Database Systems","7th edition","McGraw-Hill",""),
("A First Course in Database Systems","Jeffrey D. Ullman, Jennifer Widom","Database Systems","3rd edition","Pearson",""),
("Clean Architecture","Robert C. Martin","Software Architecture","","Prentice Hall",""),
("Patterns of Enterprise Application Architecture","Martin Fowler","Software Architecture","","Addison-Wesley",""),
("Refactoring: Improving the Design of Existing Code","Martin Fowler","Software Engineering","2nd edition","Addison-Wesley",""),
("Domain-Driven Design: Tackling Complexity in the Heart of Software","Eric Evans","Software Architecture","","Addison-Wesley",""),
("The Design of Everyday Things","Don Norman","Software Design","Revised and expanded edition","Basic Books",""),
("Code Complete","Steve McConnell","Software Engineering","2nd edition","Microsoft Press",""),
("Working Effectively with Legacy Code","Michael Feathers","Software Engineering","","Prentice Hall",""),
("Java: The Complete Reference","Herbert Schildt","Java and OOP","12th edition","McGraw-Hill",""),
("Core Java Volume I—Fundamentals","Cay S. Horstmann","Java and OOP","11th edition","Pearson",""),
("Data Structures and Algorithms in Java","Robert Lafore","Data Structures and Algorithms","2nd edition","Sams Publishing",""),
("Algorithms","Robert Sedgewick, Kevin Wayne","Data Structures and Algorithms","4th edition","Addison-Wesley",""),
("Modern Operating Systems","Andrew S. Tanenbaum, Herbert Bos","Operating Systems","4th edition","Pearson",""),
("Computer Networking: A Top-Down Approach","James F. Kurose, Keith W. Ross","Computer Science","8th edition","Pearson",""),
("The Mythical Man-Month","Frederick P. Brooks Jr.","Software Engineering","Anniversary edition","Addison-Wesley",""),
]

# Only ISBNs checked against publisher catalogue records are populated.
VERIFIED_ISBNS = {"9780201895513", "9780131489066"}

def seed_database(db):
    for i, row in enumerate(BOOKS):
        title,authors,category,edition,publisher,isbn=row
        clean_isbn=isbn if isbn in VERIFIED_ISBNS else None
        if title == "Object-Oriented Analysis and Design" and authors == "Ali Bahrami":
            # Preserve the requested attribution while removing earlier unverified details.
            db.execute("UPDATE books SET edition=NULL,publisher=NULL,isbn=NULL WHERE title=? AND authors=?",(title,authors))
        exists=db.execute("SELECT 1 FROM books WHERE title=? AND authors=? LIMIT 1",(title,authors)).fetchone()
        if not exists:
            db.execute("INSERT OR IGNORE INTO books(title,authors,category,edition,publisher,isbn,description,cover,total_copies,available_copies,shelf) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (title,authors,category,edition or None,publisher,clean_isbn,f"A well-known reference for students studying {category.lower()}. Bibliographic details are recorded when verified; stock and shelf are illustrative local-library inventory.","",3+(i%4),1+(i%3),f"CS-{(i//5)+1:02d}-{(i%5)+1:02d}"))
