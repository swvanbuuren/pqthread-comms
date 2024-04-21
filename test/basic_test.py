""" Test the pqthread_comms container module """

import pytest
from example import gui_worker


def test_basic():
    """ Basic functionality check, should not raise any errors """

    def worker(agency: gui_worker.GUIAgency):
        """ Helper function """
        ft = gui_worker.FigureTools(agency)
        fig = ft.figure()
        fig.close()

    gui_worker.GUIAgency(worker=worker)


def test_method_return():
    """ Test return value of method call from the worker thread """

    def worker(agency: gui_worker.GUIAgency):
        """ Helper function """
        ft = gui_worker.FigureTools(agency)
        fig = ft.figure()
        title = fig.change_title('Hello from worker')
        fig.close()
        return title

    agency = gui_worker.GUIAgency(worker=worker)
    assert agency.result == 'Figure 1: Hello from worker'


def test_multiple_figure_closure():
    """ Test closure of multiple figures """

    def worker(agency: gui_worker.GUIAgency):
        """ Helper function """
        ft = gui_worker.FigureTools(agency)
        fig1 = ft.figure()
        fig2 = ft.figure()
        fig1.close()
        fig2.close()

    try:
        gui_worker.GUIAgency(worker=worker)
    except IndexError:
        pytest.fail("Unexpected IndexError")