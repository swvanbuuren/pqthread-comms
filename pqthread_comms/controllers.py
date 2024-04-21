"""
Module for controlling of and communication between worker and GUI thread. It
provides a base class for controllers that control the communication between a
worker thread and the GUI thread.
"""

import sys
from pqthread_comms.qt import QtCore, QtWidgets
from pqthread_comms import agents
from pqthread_comms import utils
from pqthread_comms import containers


class WorkerAgency(QtCore.QObject):
    """ Owns all worker agents """
    error = QtCore.Signal()

    def __init__(self, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.worker_agents = {}
        if worker_agents := kwargs.get('agents'):
            for name, agent in worker_agents.items():
                self.worker_agents[name] = agent

    def add_agent(self, name):
        """ Adds a new sender """
        self.worker_agents[name] = agents.WorkerAgent(name, parent=self)

    def agent(self, name):
        """ Returns the worker agent """
        return self.worker_agents[name]


class FunctionWorker(QtCore.QObject):
    """ Worker thread that runs a user-supplied function """
    finished = QtCore.Signal()

    def __init__(self, function, agency, *args, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.function = function
        self.agency = agency
        self.args = args
        self.kwargs = kwargs
        self.result = None

    @QtCore.Slot()
    def run(self):
        """ Run the function with exception handling """
        try:
            self.result = self.function(self.agency, *self.args, **self.kwargs)
        except BaseException:
            (exception_type, value, traceback) = sys.exc_info()
            sys.excepthook(exception_type, value, traceback)
            self.agency.error.emit()
        finally:
            self.finished.emit()


class GUIAgency(QtCore.QObject):
    """ Controller class which coordinates all figure and axis objects """
    gui_agents = {}
    worker_agents = []

    @classmethod
    def add_gui_items(cls, **gui_items):
        """ Add GUI items """
        for name, item in gui_items.items():
            container = containers.GUIItemContainer(item)
            cls.add_single_gui_container(name, container)
        return cls

    @classmethod
    def add_gui_containers(cls, **gui_containers):
        """ Add GUI item container """
        for name, container in gui_containers.items():
            cls.add_single_gui_container(name, container)
        return cls

    @classmethod
    def add_single_gui_container(cls, name, container):
        """ Add GUI item container """
        cls.gui_agents[name] = agents.GUIAgent(container)
        cls.add_worker_agents(name)
        return cls

    @classmethod
    def add_worker_agents(cls, *worker_agents):
        """ Add worker agents """
        for agent in worker_agents:
            cls.worker_agents.append(agent)
        return cls

    def __init__(self, worker, *args, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.result = None
        self.exception_raised = False
        self.raised_exception = None
        if not QtWidgets.QApplication.instance():
            self.application = QtWidgets.QApplication(sys.argv)
        else:
            self.application = QtWidgets.QApplication.instance()
        self.thread = QtCore.QThread(parent=self)
        self.worker_agency = WorkerAgency()
        self.worker = FunctionWorker(worker, self.worker_agency, *args, **kwargs)
        self.setup_worker()
        self.execute()

    def setup_worker(self):
        """ Setup worker thread """
        # add worker agents
        for worker_agent in self.worker_agents:
            self.worker_agency.add_agent(worker_agent)
        self.worker.moveToThread(self.thread)
        self.worker_agency.error.connect(self.worker_exception)
        self.worker_agency.moveToThread(self.thread)
        # connect agents
        for name, agent in self.gui_agents.items():
            self.worker_agency.agent(name).connect_agent(agent)
        # connect other signals/slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.fetch_worker_result)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.thread.wait)
        self.worker.finished.connect(self.worker_agency.deleteLater)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.thread.deleteLater)

    def excepthook(self, exc_type, exc_value, exc_tb):
        """ Catch any exception and print it """
        self.raised_exception = (exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        self.application.exit()

    def execute(self):
        """ Create QApplication, start worker thread and the main event loop """
        self.thread.start()
        try:
            sys.excepthook = self.excepthook
            utils.compat_exec(self.application)
        except agents.WorkerAgentException:
            if not self.exception_raised:
                raise
            self.exception_raised = False
        else:
            if self.raised_exception:
                exc_type, exc_value, exc_tb = self.raised_exception
                raise exc_type(exc_value).with_traceback(exc_tb)
        finally:
            self.application.exit()

    @QtCore.Slot()
    def fetch_worker_result(self):
        """ Slot to fetch worker result """
        self.result = self.worker.result

    @QtCore.Slot()
    def worker_exception(self):
        """ Slot to react on a work exception """
        self.exception_raised = True