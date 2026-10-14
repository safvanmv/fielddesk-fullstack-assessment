from .tasks import notify_technician


def enqueue_assignment_notification(work_order_id):
    notify_technician.delay(str(work_order_id))
