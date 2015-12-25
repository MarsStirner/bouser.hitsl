# -*- coding: utf-8 -*-
import datetime

__author__ = 'viruzzz-kun'


def errand_statuses(self):
    from .models import Errand, rbErrandStatus

    with self.db.context_session() as session:
        session.query(Errand).filter(
            Errand.deleted == 0,
            rbErrandStatus.code == 'waiting',
            Errand.plannedExecDate < datetime.date.today(),
            Errand.status_id == rbErrandStatus.id,
        ).update({
            Errand.status_id: session.query(rbErrandStatus).filter(rbErrandStatus.code == u'expired').first().id
        }, synchronize_session=False)
