import logging

import pyodbc

from lib.connector import AuditConnector

logger = logging.getLogger("connectors/sccm")  # pylint:disable=invalid-name

#  http://www.mssccm.com/category/sccm-reports-sccm-sql-queries/
#
MainSQL = """
SELECT cs.ResourceID AS resource_id,
       cs.Name0 AS computer_name,
       cs.Domain0 AS domain_name,
       cs.Manufacturer0 AS make,
       cs.Model0 AS model,
       cs.SystemType0 AS platform,
       cs.UserName0 AS user_name,
       processor.Name0 AS cpu,
       disc.Size0 AS hdd_total_mb,
       net.IPAddress0 AS ipv4_address,
       net.MACAddress0 AS mac_address,
       mem.TotalPhysicalMemory0 AS memory_total_kb,
       enc.SerialNumber0 AS serial_number,
       os.Caption0 AS os_version
  FROM dbo.v_GS_COMPUTER_SYSTEM AS cs
    LEFT OUTER JOIN dbo.v_GS_PROCESSOR AS processor ON cs.ResourceID = processor.ResourceID
            AND processor.GroupID = 1
    LEFT OUTER JOIN dbo.v_GS_DISK AS disc ON cs.ResourceID = disc.ResourceID
    LEFT OUTER JOIN dbo.v_GS_NETWORK_ADAPTER_CONFIGURATION AS net ON cs.ResourceID = net.ResourceID
            AND MACAddress0 IS NOT NULL
            AND IPAddress0 IS NOT NULL
    LEFT OUTER JOIN dbo.v_GS_X86_PC_MEMORY AS mem ON cs.ResourceID = mem.ResourceID
    LEFT OUTER JOIN dbo.v_GS_SYSTEM_ENCLOSURE AS enc ON cs.ResourceID = enc.ResourceID
    LEFT OUTER JOIN dbo.v_GS_OPERATING_SYSTEM AS os ON cs.ResourceID = os.ResourceID;"""

SoftwareSQL = """
SELECT DisplayName0 AS 'name',
       Version0 AS 'version',
       Publisher0 AS 'publisher'
  FROM dbo.v_GS_ADD_REMOVE_PROGRAMS
 WHERE ResourceID = ?
UNION
SELECT DisplayName0 AS 'name',
       Version0 AS 'version',
       Publisher0 AS 'publisher'
  FROM dbo.v_GS_ADD_REMOVE_PROGRAMS_64
 WHERE ResourceID = ?
 """
class Connector(AuditConnector):
    MappingName = 'SCCM'
    Settings = {
        'server':            {'order': 1, 'example': 'server.example.com'},
        'database':          {'order': 2, 'default': 'CM_DCT'},
        'username':          {'order': 3, 'example': 'change-me'},
        'password':          {'order': 4, 'example': 'change-me'},
        'authentication':    {'order': 5, 'default': "SQL Server", 'choices': ("SQL Server", "Windows")},
        'sync_field':        {'order': 6, 'example': '24DCF85294E411E38A52066B556BA4EE'},
    }
    DefaultConverters = {
        # FORMAT: "{source field}": "{converter to be applied by default}",
    }
    FieldMappings = {
        'APPLICATIONS':      {'source': "software"},
    }

    def __init__(self, section, settings):
        super(Connector, self).__init__(section, settings)
        self.db = None

    def do_test_connection(self, options):
        try:
            self.authenticate()
            return {'result': True, 'error': ''}
        except Exception as exp:
            return {'result': False, 'error': 'Connection Failed: %s' % (exp.message)}

    def authenticate(self):
        """
        Connect to the database using Windows or SQL Server authentication
        :return: Connection object
        """
        if self.db:
            return

        connect_args = {
            "driver": "{SQL Server}",
            "server": self.settings['server'],
            "database": self.settings['database'],
        }
        if self.settings['authentication'] == "Windows":
            connect_args['trusted_connection'] = "yes"
        else:
            connect_args["user"] = self.settings['username']
            connect_args["password"] = self.settings['password']

        self.db = pyodbc.connect(**connect_args)

    def query(self, sql, *args):
        """
        Performs a database query with connected database.
        :param sql: SQL query
        :return: Array of dictionaries
        """
        try:
            cursor = self.db.cursor()
            results = cursor.execute(sql, args)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in results.fetchall()]
        except Exception as exception:
            logger.error("Unable to perform query: %s" % (exception))
            return []

    def _load_records(self, options):
        """
        Generate audit payload for each unique computer resource.
        """
        for resource in self.query(MainSQL):
            yield self.build_audit(resource)

    def build_audit(self, resource):
        """
        Creates an audit object using several related tables in SCCM.
        :return: Dictionary
        """
        try:
            # prepare audit structure
            audit = {
                "hardware": resource,
                "software": self.get_installed_software(resource['resource_id'])
            }

            return audit
        except Exception:
            logger.exception("Unhandled exception in build audit")
            return None

    def get_installed_software(self, resource_id):
        """
        Fetches the installed software that is registered in Add or Remove Programs
        :return: Array of dictionaries
        """
        installed_software = []
        results = self.query(SoftwareSQL, resource_id, resource_id)

        for software in results:
            try:
                software_name = software.get('name')
                if software_name in [None, ""]:
                    continue
                installed_software.append({
                    "name": software_name,
                    "version": software.get("version"),
                    "publisher": software.get("publisher"),
                    "path": None
                })
            except:
                logger.exception("Exception in get_installed_software")

        return installed_software

