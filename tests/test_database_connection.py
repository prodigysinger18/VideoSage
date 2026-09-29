import threading
import unittest
from unittest.mock import patch

from backend.database.connection import DatabaseConnection


class FakeManager:
    instances = []

    def __init__(self, config):
        self.connection = None
        self.closed = False
        FakeManager.instances.append(self)

    def connect(self):
        self.connection = object()
        return self

    def close(self):
        self.closed = True
        self.connection = None


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        FakeManager.instances = []

    def test_each_thread_gets_an_independent_connection(self):
        with patch("backend.database.connection.SQLServerManager", FakeManager):
            database = DatabaseConnection()
            main_connection = database.get()
            worker_connections = []
            worker = threading.Thread(target=lambda: worker_connections.append(database.get()))
            worker.start()
            worker.join()
            self.assertIsNot(main_connection, worker_connections[0])
            self.assertEqual(len(FakeManager.instances), 2)
            database.close()
            self.assertTrue(all(manager.closed for manager in FakeManager.instances))

    def test_close_current_only_closes_calling_thread(self):
        with patch("backend.database.connection.SQLServerManager", FakeManager):
            database = DatabaseConnection()
            database.get()
            database.close_current()
            self.assertTrue(FakeManager.instances[0].closed)


if __name__ == "__main__":
    unittest.main()
