# -*- coding: utf-8 -*-
from collections import OrderedDict
import os
import re

import tablib
import wx
import wx.grid

from dialogs import CrawlDialog
from events import ID_NEW_URL, ID_NEW_DATA, ID_NEW_NOTE, ID_START_CRAWL
from grids import URLGrid
from menus import MainMenu
from models import URL, URLData, base
from threads import Dispatcher


class Main(wx.Frame):
    """
    The main application view
    """
    
    def __init__(self, parent=None, title='Python Crawler'):
        wx.Frame.__init__(self, parent=parent, title=title)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.Panel(self, wx.ID_ANY)
        self.panel.SetSizer(sizer)
        self.urls = OrderedDict()
        self.counter = 0;
        self.CreateStatusBar()
        
        # set up menus
        self.menu = MainMenu()
        self.SetMenuBar(self.menu)
        
        # set up the grid
        self.grid = URLGrid(sizer, self.panel)
        
        # Bind menu events
        self.Bind(wx.EVT_MENU, self.menu_exit, self.menu.file_menu.exit)
        self.Bind(wx.EVT_MENU, self.menu_new, self.menu.file_menu.new_crawl)
        self.Bind(wx.EVT_MENU, self.menu_save, self.menu.file_menu.export)
        self.Bind(wx.EVT_MENU, self.menu_stop, self.menu.file_menu.stop)
        
        # Bind events from worker thread
        self.Connect(-1, -1, ID_NEW_URL, self.event_url)
        self.Connect(-1, -1, ID_NEW_DATA, self.event_data)
        self.Connect(-1, -1, ID_NEW_NOTE, self.event_note)
        self.Connect(-1, -1, ID_START_CRAWL, self.event_start)
        
        self.dispatcher = None
        
        self.Show()
        
    def menu_exit(self, event):
        self.Close(True)
    
    def menu_new(self, event):
        dlg = CrawlDialog(None, title="Start a New Crawl", size=(400, 300))
        dlg.ShowModal()
        dlg.Destroy()
    
    def menu_stop(self, event):
        if self.dispatcher is not None:
            self.dispatcher.signal_queue.put(('stop', True))
            self.SetStatusText('Stopping crawl, no new URLs will be added')
        else:
            self.SetStatusText('Start a crawl first.')
    
    def menu_save(self, event):
        if not self.urls:
            self.SetStatusText('Nothing here yet!')
            return
        dialog = wx.FileDialog(self, message='Choose a file', 
                        style=wx.FD_SAVE,
                            wildcard='Comma Separated (*.csv)|*.csv|'
                                'JSON (*.json)|*.json|YAML (*.yaml)|*.yaml')
        if dialog.ShowModal() == wx.ID_OK:
            index = dialog.GetFilterIndex()
            self.filetype = ['csv', 'json', 'yaml'][index]
            self.dirname = dialog.GetDirectory()
            filename = dialog.GetFilename()
            self.filename = '{}.{}'.format(filename, self.filetype)
            self.full_path = os.path.join(self.dirname, self.filename)
            headers = []
            for key in self.grid.get_cols().keys():
                headers.append(key)
            dataset = tablib.Dataset(headers=headers)
            for url, row in self.urls.items():
                rv = [url]
                for h in headers[1:]:
                    col = self.grid.get_col_data(h)
                    value = self.grid.GetCellValue(row, col[0])
                    rv.append(value)
                dataset.append(rv)
            try:
                with open(self.full_path, 'wb') as f:
                    if 'json' == self.filetype:
                        f.write(dataset.json)
                    elif 'yaml' == self.filetype:
                        f.write(dataset.yaml)
                    else:
                        f.write(dataset.csv)
            except Exception, e:
                self.SetSatusText('An error occured: {}'.format(e))
        else:
            self.SetStatusText('No saving?')
    
    def event_url(self, event):
        self.urls[event.url] = self.counter
        self.grid.AppendRows(1)
        self.grid.SetCellValue(self.counter, 0, event.url)
        self.counter += 1
    
    def event_data(self, event):
        row = self.urls.get(event.url)
        if row is None:
            return # probably should do something here?
        for key, value in event.data.items():
            col = self.grid.get_col_data(key)
            if col is None:
                continue
            if isinstance(value, basestring):
                value = value.encode('ascii', 'ignore')
            else:
                value = str(value)
            self.grid.SetCellValue(row, col[0], value)
    
    def event_note(self, event):
        row = self.urls.get(event.url)
        if row is None:
            return
        col = self.grid.get_col_data('notes')
        self.grid.SetCellValue(row, col[0], event.note)
    
    def event_start(self, event):
        self.dispatcher = Dispatcher(gui=self, 
                           fetchers=event.fetchers, base=event.start_url)
        self.dispatcher.signal_queue.put(('add_urls', [event.start_url]))
        self.dispatcher.start()
        self.SetStatusText('Crawling...')
