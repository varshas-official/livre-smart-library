import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app
from database import get_db, init_db
from seed import seed_database
from werkzeug.security import generate_password_hash
from dsa_algorithms import ChainedHashTable, FIFOQueue, BinarySearchTree, merge_sort


class DSAStructureTests(unittest.TestCase):
    def test_chained_hash_table_insert_update_and_missing_key(self):
        table = ChainedHashTable(capacity=3)
        table.insert("ID:1", {"id": 1})
        table.insert("ID:2", {"id": 2})
        table.insert("ID:3", {"id": 3})
        self.assertEqual(table.get("id:1")["id"], 1)
        self.assertEqual(table.get("missing"), None)
        table.insert("id:1", {"id": 10})
        self.assertEqual(table.get("ID:1")["id"], 10)
        value, comparisons = table.get_with_comparisons("ID:2")
        self.assertEqual(value["id"], 2)
        self.assertGreaterEqual(comparisons, 1)

    def test_bst_in_order_and_merge_sort(self):
        rows = [{"id": 1, "title": "Zebra"}, {"id": 2, "title": "apple"}, {"id": 3, "title": "Mango"}]
        tree = BinarySearchTree()
        for row in rows:
            tree.insert(row)
        self.assertEqual([r["title"] for r in tree.in_order()], ["apple", "Mango", "Zebra"])
        sorted_rows, comparisons = merge_sort(rows, key=lambda r: r["title"].casefold())
        self.assertEqual([r["title"] for r in sorted_rows], ["apple", "Mango", "Zebra"])
        self.assertGreaterEqual(comparisons, 2)

    def test_fifo_queue_wraparound_and_empty(self):
        queue = FIFOQueue(3)
        self.assertIsNone(queue.dequeue())
        queue.enqueue("A"); queue.enqueue("B"); queue.enqueue("C")
        self.assertEqual(queue.dequeue(), "A")
        queue.enqueue("D")
        self.assertEqual(queue.to_list(), ["B", "C", "D"])
        with self.assertRaises(OverflowError):
            queue.enqueue("E")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-key", "DATABASE": os.path.join(self.temp.name, "test.sqlite3")})
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db(); seed_database(get_db())
            db = get_db()
            db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("student","s@example.test","Test Student",generate_password_hash("test-pass")))
            db.execute("INSERT INTO users(username,email,full_name,password_hash) VALUES(?,?,?,?)",("student2","s2@example.test","Second Student",generate_password_hash("test-pass-2")))
        self.client.post("/api/login", json={"identity":"student","password":"test-pass"})

    def tearDown(self):
        self.temp.cleanup()

    def test_dsa_routes(self):
        lookup = self.client.get("/api/dsa/lookup?key=ID%3A1")
        self.assertEqual(lookup.status_code, 200)
        self.assertTrue(lookup.json["found"])
        self.assertEqual(lookup.json["book"]["id"], 1)
        catalogue = self.client.get("/api/dsa/catalogue?limit=60")
        self.assertEqual(catalogue.status_code, 200)
        titles = [b["title"].casefold() for b in catalogue.json["items"]]
        self.assertEqual(titles, sorted(titles))
        analysis = self.client.get("/api/dsa/analysis")
        self.assertEqual(analysis.status_code, 200)
        self.assertGreaterEqual(analysis.json["linear_search_comparisons"], 1)
        self.assertGreaterEqual(analysis.json["hash_lookup_comparisons"], 1)

    def test_reservation_fifo_priority(self):
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE books SET total_copies=1,available_copies=0 WHERE id=1")
        first = self.client.post("/api/reservations", json={"book_id": 1})
        self.assertEqual(first.status_code, 201, first.json)
        second_client = self.app.test_client()
        second_client.post("/api/login", json={"identity":"student2","password":"test-pass-2"})
        second = second_client.post("/api/reservations", json={"book_id": 1})
        self.assertEqual(second.status_code, 201, second.json)
        self.assertEqual(first.json["queue_position"], 1)
        self.assertEqual(second.json["queue_position"], 2)
        with self.app.app_context():
            get_db().execute("UPDATE books SET available_copies=1 WHERE id=1")
        self.assertEqual(second_client.post("/api/borrowings", json={"book_id": 1}).status_code, 400)
        self.assertEqual(self.client.post("/api/borrowings", json={"book_id": 1}).status_code, 201)
        second_reservation = second_client.post("/api/reservations", json={"book_id": 1})
        self.assertEqual(second_reservation.status_code, 201 if second_reservation.json.get("reservation_id") else 409)
        self.assertEqual(second_client.delete("/api/reservations/2").status_code, 200)


if __name__ == "__main__":
    unittest.main()
