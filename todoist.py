from collections import OrderedDict
import logging
from todoist_api_python.api import TodoistAPI


class Todoist:

  def __init__(self, token):
    self.api = TodoistAPI(token)
    self.project_map = None
    self.task_map = None

  def get_project(self, id):
    try:
      if not self.project_map:
        logging.info('updating map')
        projects = self.api.get_projects()
        self.project_map = { p.id:p for p in projects}
      return self.project_map[id]
    except Exception as error:
      logging.error(error)
      exit(1)

  def get_task(self, id):
    try:
      if not self.task_map:
        self.task_map = { t.id: t for t in self.api.get_tasks() }
      return self.task_map[id]
    except Exception as error:
      logging.error(error)
      exit(1)

  def get_tasks(self):
    try:
      if not self.task_map:
        tasks = sorted(self.api.get_tasks(), key=lambda x: x.order)
        self.task_map = OrderedDict((t.id, t) for t in tasks)
      return self.task_map.values()
    except Exception as error:
      logging.error(error)
      exit(1)

  def get_comments_for(self, task_id):
    return self.api.get_comments(task_id=task_id)
