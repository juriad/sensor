import sqlite3

from .database import Database
from ..sensor.sensor import Sensor, CycleInterval

with sqlite3.connect('metriful.db') as con:
    db = Database(con)

    with Sensor() as sensor:
        sensor.cycle(CycleInterval.T_3_S)
        while True:
            sensor.wait_for_ready()

            data = sensor.read_data(True)
            print(data)
            db.insert(data)
