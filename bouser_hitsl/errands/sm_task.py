# -*- coding: utf-8 -*-
import datetime

__author__ = 'viruzzz-kun'


def errand_statuses(self):
    from .models import Errand, rbErrandStatus

    with self.db.context_session() as session:
        now = datetime.datetime.now()
        to_update = session.query(Errand).join(rbErrandStatus).filter(Errand.deleted == 0, rbErrandStatus.code == 'waiting').all()
        for errand in to_update:
            if errand.plannedExecDate.date() < now.date() and not errand.execDate:
                errand.status = session.query(rbErrandStatus).filter(rbErrandStatus.code == 'expired').first()
                session.add(errand)
        session.commit()