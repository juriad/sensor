import datetime
import sqlite3


class Database:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

        con.execute("""PRAGMA journal_mode=WAL""")

        con.execute("""
        CREATE TABLE IF NOT EXISTS "metriful" (
            "timestamp" TEXT,
            
            "T_C" REAL,
            "P_Pa" INTEGER,
            "H_pc" REAL,
            "G_ohm" INTEGER,
            
            "AQI" REAL,
            "AQI_value" TEXT,
            "CO2e" REAL,
            "bVOC" REAL,
            "AQI_accuracy" TEXT,
            
            "illum_lux" REAL,
            "white" INTEGER,
            
            "SPL_dBA" REAL,
            "SPL_bands_dB_1" REAL,
            "SPL_bands_dB_2" REAL,
            "SPL_bands_dB_3" REAL,
            "SPL_bands_dB_4" REAL,
            "SPL_bands_dB_5" REAL,
            "SPL_bands_dB_6" REAL,
            "peak_amp_mPa" REAL,
            "stable" TEXT,
            
            "duty_cycle_pc" REAL,
            "concentration" REAL,
            "conc_unit" TEXT,
            "valid" TEXT
        )
        """)

    def insert(self, values: dict):
        self.con.execute(
            """INSERT INTO "metriful" VALUES (?, ?,?,?,?, ?,?,?,?,?, ?,?, ?,?,?,?,?,?,?,?,?, ?,?,?,?)""",
            [
                str(datetime.datetime.now().astimezone()),

                values.get('T_C'),
                values.get('P_Pa'),
                values.get('H_pc'),
                values.get('G_ohm'),

                values.get('AQI'),
                Db.enum_name(values.get('AQI_value')),
                values.get('CO2e'),
                values.get('bVOC'),
                Db.enum_name(values.get('AQI_accuracy')),

                values.get('illum_lux'),
                values.get('white'),

                values.get('SPL_dBA'),
                values.get('SPL_bands_dB_1'),
                values.get('SPL_bands_dB_2'),
                values.get('SPL_bands_dB_3'),
                values.get('SPL_bands_dB_4'),
                values.get('SPL_bands_dB_5'),
                values.get('SPL_bands_dB_6'),
                values.get('peak_amp_mPa'),
                Db.enum_name(values.get('stable')),

                values.get('duty_cycle_pc'),
                values.get('concentration'),
                values.get('conc_unit'),
                Db.enum_name(values.get('valid'))
            ]
        )

    @staticmethod
    def enum_name(value):
        return value.name if value is not None else None
