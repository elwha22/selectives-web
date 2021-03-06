import os
import urllib
import jinja2
import webapp2
import logging
import yayv


import models
import authorizer

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


schema = yayv.ByExample(
    "- name: UNIQUE\n"
    "  row: REQUIRED\n"
    "  col: REQUIRED\n"
    "  rowspan: OPTIONAL\n"
    "  colspan: OPTIONAL\n")


class Dayparts(webapp2.RequestHandler):

  def RedirectToSelf(self, institution, session, message):
    self.redirect("/dayparts?%s" % urllib.urlencode(
        {'message': message, 
         'institution': institution,
         'session': session}))

  def post(self):
    auth = authorizer.Authorizer(self)
    if not auth.CanAdministerInstitutionFromUrl():
      auth.Redirect()
      return

    institution = self.request.get("institution")
    if not institution:
      logging.fatal("no institution")
    session = self.request.get("session")
    if not session:
      logging.fatal("no session")
    dayparts = self.request.get("dayparts")
    if not dayparts:
      logging.fatal("no dayparts")
    dayparts = schema.Update(dayparts)
    models.Dayparts.store(institution, session, dayparts)
    self.RedirectToSelf(institution, session, "saved dayparts")

  def get(self):
    auth = authorizer.Authorizer(self)
    if not auth.CanAdministerInstitutionFromUrl():
      auth.Redirect()
      return

    institution = self.request.get("institution")
    if not institution:
      logging.fatal("no institution")
    session = self.request.get("session")
    if not session:
      logging.fatal("no session")

    logout_url = auth.GetLogoutUrl(self)
    message = self.request.get('message')
    session_query = urllib.urlencode({'institution': institution,
                                      'session': session})
    dayparts = models.Dayparts.fetch(institution, session)
    if not dayparts:
      dayparts = '\n'.join([
          "# Sample data. Lines with leading # signs are comments.",
          "# Change the data below.",
          "- name: Mon A",
          "  row: 1",
          "  col: 1",
          "  rowspan: 1",
          "  colspan: 1",
          "- name: Tues A",
          "  row: 1",
          "  col: 2",
          "- name: Thurs A",
          "  row: 1",
          "  col: 3",
          "- name: Fri A",
          "  row: 1",
          "  col: 4",
          "- name: Mon B",
          "  row: 2",
          "  col: 1",
          "- name: Tues B",
          "  row: 2",
          "  col: 2",
          "- name: Thurs B",
          "  row: 2",
          "  col: 3",
          "- name: Fri B",
          "  row: 2",
          "  col: 4",])

    template_values = {
      'logout_url': logout_url,
      'user_email' : auth.email,
      'institution' : institution,
      'session' : session,
      'message': message,
      'session_query': session_query,
      'dayparts': dayparts,
      'self': self.request.uri,
    }
    template = JINJA_ENVIRONMENT.get_template('dayparts.html')
    self.response.write(template.render(template_values))
