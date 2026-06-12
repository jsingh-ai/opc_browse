from fastapi import APIRouter

from opc_browse.db import connection_context
from opc_browse.models import MachineOut


router = APIRouter(tags=["machines"])


@router.get("/machines", response_model=list[MachineOut])
def list_machines():
    sql = """
        SELECT id, machine_name, endpoint_url, enabled
        FROM machines
        WHERE enabled = %s
        ORDER BY machine_name ASC
    """
    with connection_context() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (1,))
            rows = cursor.fetchall()
    return rows
