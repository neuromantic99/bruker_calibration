from PyQt5.QtWidgets import (QWidget, QLabel, 
    QComboBox, QApplication, QHBoxLayout, QVBoxLayout, QGridLayout,QPushButton)
from PyQt5.QtGui import QPixmap, QMovie, QFont
from PyQt5.QtCore import QSize, QRect    
import sys
import win32com.client
import datetime
import os
import subprocess
import time

class startup_gui(QWidget):
    
    def __init__(self):
        super().__init__()
        self.initUI()
        self.build_text()
        self.build_dropdown()
        self.build_gif()
        
        #whether the try again and continue buttons are already present
        self.buttons_present = False
        self.show()

    def initUI(self):
        self.setWindowTitle('Packer1')
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        
    def build_text(self):
        
        self.header_text = QLabel()
        self.header_text.setText('                 Hello, welcome to Packer1 \nPlease start PrairieView and select your name below')
        font = QFont("Helvetica", 15) 
        self.header_text.setFont(font)
        self.grid.addWidget(self.header_text, 1,1)
        

    def build_gif(self):   
       
        self._gif = QLabel()
        p_gif = QMovie('p.gif')
        self._gif.setMovie(p_gif)
        p_gif.start()
            
        self.grid.addWidget(self._gif,1,0)
        
        self._gif = QLabel()
        p_gif = QMovie('p.gif')
        self._gif.setMovie(p_gif)
        p_gif.start()
            
        self.grid.addWidget(self._gif,1,2)


    def build_dropdown(self):
    
        combo = QComboBox(self)
        combo.addItem('')
        combo.addItem('Adam')
        combo.addItem('Jimmy')
        combo.addItem('Rob')
        combo.addItem('Andrew')
        combo.setMaximumWidth(1000)
        self.grid.addWidget(combo, 2,1)
      
        combo.activated[str].connect(self.got_username) 
        

    def got_username(self, text):
        if text == '':
            #do not continue if user accidently presses blank list option
            self.build_dropdown()       
        else:
            self.user_name = text
            self.create_folders()
            self.header_text.setText('Hi {}, I\'m setting up your folders and txt file for today \nIf you would like to set up PrairieView click the button below'.format(self.user_name))
            
        if not self.buttons_present:
            self.pl_button = QPushButton("Set up PrairieView")
            self.pl_button.toggle()
            self.pl_button.clicked.connect(lambda: self.setup_prairie())
            self.grid.addWidget(self.pl_button,3,0)
 
                    
    def create_folders(self):
        now = datetime.datetime.now()
        self.date_today = now.strftime('%Y-%m-%d')
        if self.user_name == 'Jimmy':
            self.local_path = r'F:\Data\jrowland\{}'.format(self.date_today)
            self.pstation_path = r'Z:\jrowland\Data\{}'.format(self.date_today)
        elif self.user_name == 'Adam':
            self.local_path = r'F:\Data\apacker\{}'.format(self.date_today)
            self.pstation_path = r'Z:\apacker\{}'.format(self.date_today)
            
            
        if not os.path.exists(self.local_path):
            os.makedirs(self.local_path)
        if not os.path.exists(self.pstation_path):
            os.makedirs(self.pstation_path)
            
        # open the folders in explorer
        subprocess.Popen('explorer "{0}"'.format(self.local_path))
        subprocess.Popen('explorer "{0}"'.format(self.pstation_path))
        time.sleep(0.5)
        
        new_text_file = os.path.join(self.local_path, self.date_today + '_packer1.txt')
        
        if not os.path.exists(new_text_file):
            f = open(new_text_file, 'w')
            f.close()     
            subprocess.Popen('notepad "{0}"'.format(new_text_file))
        
        
        

    def setup_prairie(self):       
        # Start PrairieLink      
        try:
            pl = win32com.client.Dispatch('PrairieLink.Application')
            pl.Connect()
            pl.SendScriptCommands('-SetSavePath ' + self.local_path)
            pl.SendScriptCommands('-SetFileName ' + 'Singlescan ' + self.date_today + '_s')
            pl.SendScriptCommands('-SetFileName ' + 'Zseries ' + self.date_today + '_z')
            pl.SendScriptCommands('-SetFileName '  + 'Tseries ' + self.date_today + '_t')
            # set this last as it takes time
            pl.SendScriptCommands('-SetAcquisitionMode ' + 'ResonantGalvo')
        except:
            # i apologise to the python gods for the formating of this string
            self.header_text.setText('           Unfortunately I cannot connect to PrairieView right now. \nEnsure software is running and no other Prairielink scripts are active\n                                Click below to try again')
            

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    gui = startup_gui()
    sys.exit(app.exec_())
