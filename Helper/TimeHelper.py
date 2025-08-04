import datetime
import threading

class ThreadSafeFreezeTime:
    def __init__(self, frozen_time):
        self.frozen_time = frozen_time
        self._original_datetime = None

    def __enter__(self):
        self._original_datetime = datetime.datetime

        class MockDatetime(datetime.datetime):
            _frozen_time = self.frozen_time

            @classmethod
            def now(cls, tz=None):
                return cls._frozen_time.replace(tzinfo=tz)

            @classmethod
            def utcnow(cls):
                return cls._frozen_time

            def __new__(cls, *args, **kwargs):
                if not args and not kwargs:
                    return cls._frozen_time
                return super().__new__(cls, *args, **kwargs)

        datetime.datetime = MockDatetime
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        datetime.datetime = self._original_datetime