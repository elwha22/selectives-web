import models
import yaml
import logging
try:
  from google.appengine.ext import ndb
except:
  logging.info("google.appengine.ext not found. "
                "We must be running in a unit test.")
  import fake_ndb
  ndb = fake_ndb.FakeNdb()


def FindStudent(student_email, students):
  # is students iterable?
  try:
    _ = (e for e in students)
  except TypeError:
    return None
  for student in students:
    if student_email == student['email']:
      return student
  return None


def EligibleClassIdsForStudent(student, classes):
  """Return the set of class ids that the student is eligible to take."""
  class_ids = []
  for c in classes:
    class_id = str(c['id'])
    if not c['prerequisites']:
      class_ids.append(class_id)
    for prereq in c['prerequisites']:
      if 'email' in prereq:
        if student['email'] == prereq['email']:
          class_ids.append(class_id)
      if 'current_grade' in prereq:
        if student['current_grade'] == prereq['current_grade']:
          class_ids.append(class_id)
      if 'group' in prereq:
        #TODO: fix me so student groups work
        class_ids.append(class_id)
  return class_ids


class _ClassRoster(object):

  def __init__(self, institution, session, class_obj):
    self.institution = institution
    self.session = session
    self.class_obj = class_obj
    new_class_id = class_obj['id']
    roster = models.ClassRoster.FetchEntity(institution, session, new_class_id)
    self.emails = roster['emails']

  def add(self, student_email):
    self.emails.append(student_email)
    self.emails = list(set(self.emails))
    emails = ','.join(self.emails)
    logging.info("new emails in [%s]: %s" % (self.class_obj['id'], emails))
    models.ClassRoster.Store(
        self.institution, self.session, self.class_obj, emails)

  def remove(self, student_email):
    self.emails = [ e for e in self.emails if e != student_email ]
    emails = ','.join(self.emails)
    logging.info("remaining emails in [%s]: %s" % (self.class_obj['id'], emails))
    models.ClassRoster.Store(
        self.institution, self.session, self.class_obj, emails)


class _ClassInfo(object):

  def __init__(self, institution, session):
    classes = models.Classes.Fetch(institution, session)
    classes = yaml.load(classes)
    self.dayparts_by_class_id = {}
    self.classes_by_id = {}
    for c in classes:
      class_id = str(c['id'])
      self.classes_by_id[class_id] = c
      self.dayparts_by_class_id[class_id] = [s['daypart'] for s in c['schedule']]

  def getClassObj(self, class_id):
    class_obj = self.classes_by_id[class_id]
    if not class_obj:
      logging.fatal('no class_obj')
    if not 'id' in class_obj:
      logging.fatal('class_obj has no id')
    return class_obj

  def RemoveConflicts(self, class_ids, new_class_id):
    """return new_class_id and non-conflicting old class_ids""" 
    if new_class_id in self.dayparts_by_class_id:
      new_dayparts = self.dayparts_by_class_id[new_class_id]
    else:
      new_dayparts = []
    new_class_ids =  [new_class_id]
    for c_id in class_ids:
      if c_id == '':
        continue
      remove = False
      for daypart in self.dayparts_by_class_id[c_id]:
        if daypart in new_dayparts:
          remove = True
      if not remove:
        new_class_ids.append(c_id)
    return new_class_ids


class _StudentSchedule(object):

  def __init__(self, institution, session, student_email, class_info):
    """Args:
           class_info is a _ClassInfo object
    """
    self.institution = institution
    self.session = session
    self.student_email = student_email
    class_ids = models.Schedule.Fetch(institution, session, student_email)
    self.class_ids = class_ids.split(",")
    self.class_info = class_info

  def add(self, new_class_id):
    class_ids = self.class_ids
    class_ids = self.class_info.RemoveConflicts(class_ids, new_class_id)
    self.class_ids = class_ids
    self.store()

  def remove(self, old_class_id):
    class_ids = self.class_ids
    class_ids = [ i for i in class_ids if i != old_class_id ]
    self.class_ids = class_ids
    self.store()

  def store(self):
    class_ids = ",".join(self.class_ids)
    models.Schedule.Store(
        self.institution, self.session, self.student_email, class_ids)


@ndb.transactional(retries=3, xg=True)
def AddStudentToClass(institution, session, student_email, new_class_id):
  class_info = _ClassInfo(institution, session)
  s = _StudentSchedule(institution, session, student_email, class_info)
  s.add(new_class_id)
  class_obj = class_info.getClassObj(new_class_id)
  r = _ClassRoster(institution, session, class_obj)
  r.add(student_email)


@ndb.transactional(retries=3, xg=True)
def RemoveStudentFromClass(institution, session, student_email, old_class_id):
  class_info = _ClassInfo(institution, session)
  class_obj = class_info.getClassObj(old_class_id)
  r = _ClassRoster(institution, session, class_obj)
  r.remove(student_email)
  s = _StudentSchedule(institution, session, student_email)
  s.remove(class_obj['id'])
