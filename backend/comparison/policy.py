MIB = 1024 * 1024
MAX_FILE_BYTES = 10 * MIB
MAX_TOTAL_BYTES = 30 * MIB
MAX_BODY_BYTES = MAX_TOTAL_BYTES + 64 * 1024
MAX_TEXT_CHARS = 200_000
MAX_TOKENS = 30_000
MAX_ZIP_BYTES = 50 * MIB
MAX_XML_BYTES = 8 * MIB
MAX_ZIP_ENTRIES = 1000
MAX_PAGES = 200
MAX_MATCHES = 500
MAX_OPERATIONS = 300_000
MAX_RESULT_BYTES = 12 * MIB
WORKER_SECONDS = 30
UPLOAD_SECONDS = 60
MEMORY_BYTES = 512 * MIB
SHINGLE_SIZE = 5


class ComparisonError(Exception):
    def __init__(self, code, message, status=422, file=None):
        super().__init__(message)
        self.code, self.message, self.status, self.file = code, message, status, file

    def payload(self):
        return {"error": {"code": self.code, "message": self.message, "file": self.file}}
