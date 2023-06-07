#!/usr/bin/env python3

from datetime import datetime
import logging
import re
import caldav

from todoist import Todoist
from todoist_api_python.models import Task
from webcolors import name_to_hex


def due_date_from(task: Task):
  try:
    if not task.due:
      return None
    elif task.due.datetime:
      return datetime.strptime(task.due.datetime, '%Y-%m-%dT%H:%M:%S')
    elif task.due.date:
      return datetime.strptime(task.due.date, '%Y-%m-%d')
  except Exception as e:
    logging.error(f'{task.due} :  {e}')
  return None

def convert_date_unit(unit: str):
  if re.match(r'years?', unit):
    return 'YEARLY'
  if re.match(r'months?', unit):
    return 'MONTHLY'
  if re.match(r'weeks?', unit):
    return 'WEEKLY'
  if re.match(r'days?', unit):
    return 'DAILY'
  logging.error(f'unkown unit {unit}')
  return None

def convert_recurring(task: Task):
  recurr_string = todoist_task.due.string
  logging.debug(f'{task.content} searching {recurr_string}')
  fragments = re.search(r'(E|e)very!? (?P<monthday>3)rd (?P<day>Su)nday of (?P<month>November)', recurr_string)
  if fragments:
    return dict(FREQ=convert_date_unit('year'),
                BYDAY=f"{fragments.group('monthday')}{fragments.group('day').capitalize()}",
                BYMONTH=datetime.strptime(fragments.group('month'), '%B').month)

  fragments = re.search(r'every!? (?P<month>december|june|august) (?P<date>1)', recurr_string)
  if fragments:
    return dict(FREQ=convert_date_unit('year'),
                BYMONTH=datetime.strptime(fragments.group('month'), '%B').month)

  fragments = re.search(r'every!? (?P<unit>day|week|month|year)\s*(?P<time>.*)?', recurr_string)
  if fragments:
    unit = convert_date_unit(fragments.group('unit'))
    if unit:
      recur = dict(FREQ=unit)
      if fragments.group('time'):
        recur['BYHOUR'] = datetime.strptime(fragments.group('time'), '%I %p').hour
      return recur

  fragments = re.search(r'every!? (?P<interval>\d) (?P<unit>days|weeks|months)', recurr_string)
  if fragments:
    unit = convert_date_unit(fragments.group('unit'))
    if unit:
      return dict(FREQ=unit, INTERVAL=fragments.group('interval'))

  logging.error(f'For {task.content}, {recurr_string} does not match')
  return None

def convert_priority(priority: int):
  if priority == 2:
    return 8
  elif priority == 3:
    return 5
  elif priority == 4:
    return 2
  return None

def task_exists(project: caldav.Calendar, id: str):
  try:
    if project.todo_by_uid(id):
      return True
  except Exception as e:
    logging.debug(e)
  return False

def project_map(cal_dav_client: caldav.Principal):
  projects = {}
  for l in cal_dav_client.calendars():
    l.id = l.canonical_url.split('/')[-2]
    projects[l.id] = l
  return projects

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')

  cal_dav_server = ''
  username = ''
  password = ''
  url = f'https://{cal_dav_server}/{username}'

  todoist = Todoist('')

  with caldav.DAVClient(url=url, username=username, password=password) as cal_dav_connection:
    cal_dav_client = cal_dav_connection.principal()

    projects = project_map(cal_dav_client)
    for todoist_task in todoist.get_tasks():
      todoist_project = todoist.get_project(todoist_task.project_id)
      logging.debug(f'Ensure project {todoist_project.name} exists')

      if todoist_task.project_id not in projects.keys():
        try:
          colour = name_to_hex(todoist_project.color)
        except Exception as e:
          logging.error(f'{todoist_project.name} {e}')
          colour = '#000000'
        project_name = todoist_project.name
        parent_id = todoist_project.parent_id
        while parent_id:
          parent_project = todoist.get_project(parent_id)
          project_name = f'{parent_project.name} - {project_name}'
          parent_id = parent_project.parent_id
        cal_dav_client.make_calendar(name=project_name, cal_id=todoist_project.id, supported_calendar_component_set=['VTODO']).set_properties([caldav.elements.ical.CalendarColor(colour)]).save()
        projects = project_map(cal_dav_client)

      logging.debug(f'Ensure task added')
      logging.debug(todoist_task)
      project = projects.get(todoist_task.project_id)

      task_body = dict(
        uid=todoist_task.id,
        summary=todoist_task.content,
        X_APPLE_SORT_ORDER=todoist_task.order,
      )
      if convert_priority(todoist_task.priority):
        task_body['priority'] = convert_priority(todoist_task.priority)

      description = []
      if todoist_task.description:
        description.append(todoist_task.description)
      if todoist_task.comment_count > 0:
        description += [c.content for c in todoist.get_comments_for(todoist_task.id)]
      task_body['description'] = '\n'.join(description)

      if todoist_task.due and due_date_from(todoist_task):
        logging.debug(todoist_task.due)
        task_body['due'] = due_date_from(todoist_task)
        if todoist_task.due.is_recurring:
          logging.debug(todoist_task.due)
          task_body['rrule'] = convert_recurring(todoist_task)

      if todoist_task.labels:
        task_body['categories'] = todoist_task.labels

      if todoist_task.parent_id:
        if not task_exists(project, todoist_task.parent_id):
          logging.debug(f'parent {todoist_task.parent_id} not found')
          continue
        task_body['related_to'] = todoist_task.parent_id

      todo = project.add_todo(**task_body)
