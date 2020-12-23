import sys
from Client import LoginRegisterForm, WebHandler, MessengerForm, StartConversationForm
from PyQt5 import QtCore, QtWidgets, QtGui
import enum


class ConversationType(enum.Enum):
    dialog = 0
    group = 1


class StartConversationWindow(QtWidgets.QDialog, StartConversationForm.Ui_ConversationForm):
    def __init__(self, web_handler):
        super().__init__()
        self.setupUi(self)
        self.web_handler = web_handler
        self.startDialogButton.clicked.connect(self.startDialog)
        self.dialogWindow = QtWidgets.QMessageBox()
        self.dialogWindow.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.dialogWindow.setIcon(QtWidgets.QMessageBox.Information)
        self.dialogWindow.setModal(True)

    def startDialog(self):
        person = self.personNick.text()
        result = self.web_handler.start_dialog(person)
        if result:
            self.dialogWindow.setWindowTitle("Dialog created")
            self.dialogWindow.setText("Dialog started successfully")
            self.dialogWindow.show()
            self.close()
        else:
            self.dialogWindow.setWindowTitle("Couldn't start dialog")
            self.dialogWindow.setText("Failed to start dialog")
            self.dialogWindow.show()


class MessengerWindow(QtWidgets.QMainWindow, MessengerForm.Ui_MessengerWindow):
    emitter = QtCore.pyqtSignal()

    def __init__(self, web_handler, login):
        super().__init__()
        self.setupUi(self)
        self.chatListUpdateTimer = QtCore.QTimer()
        self.chatListUpdateTimer.timeout.connect(self.updateChatList)
        self.refreshMessagesTimer = QtCore.QTimer()
        self.refreshMessagesTimer.timeout.connect(self.getNewMessages)
        self.activeChat = None
        self.web_handler = web_handler
        self.login = login
        self.chatContainer.hide()
        self.NoChatMessage.show()
        self.updateChatList()
        self.chatsList.itemSelectionChanged.connect(self.selectChat)
        self.chatListUpdateTimer.start(6000)
        self.last_message = 0
        self.sendButton.clicked.connect(self.sendMessage)
        self.startConversationButton.clicked.connect(self.startConversation)

    def updateChatList(self):
        dialogs = self.web_handler.get_all_dialogs()
        self.chatsList.clear()
        counter = 0
        for dialog in dialogs:
            dialog['conversation_type'] = ConversationType.dialog
            dialog_item = QtWidgets.QListWidgetItem()
            dialog_item.setData(QtCore.Qt.UserRole, dialog)
            if dialog['persons'][0] == self.login:
                dialog_item.setText(dialog['persons'][1])
            else:
                dialog_item.setText(dialog['persons'][0])
            self.chatsList.addItem(dialog_item)
            if self.activeChat is not None and self.activeChat['_id'] == dialog['_id']:
                self.chatsList.setCurrentIndex(self.chatsList.indexFromItem(dialog_item))
            counter += 1

    def selectChat(self):
        selected = self.chatsList.selectedItems()
        if len(selected) > 0:
            if self.activeChat is None or selected[0].data(QtCore.Qt.UserRole)['_id'] != self.activeChat['_id']:
                self.refreshMessagesTimer.stop()
                self.activeChat = selected[0].data(QtCore.Qt.UserRole)
                if self.activeChat['persons'][0] == self.login:
                    self.chatLabel.setText(self.activeChat['persons'][1])
                else:
                    self.chatLabel.setText(self.activeChat['persons'][0])
                for i in reversed(range(self.verticalLayout_6.count())):
                    self.verticalLayout_6.itemAt(i).widget().setParent(None)
                self.chatContainer.show()
                self.NoChatMessage.hide()
                messages = self.web_handler.get_dialog_messages(self.activeChat['_id'])
                if len(messages) > 0:
                    for message in messages:
                        self.addMessage(message['sender'], message['content'])
                    self.last_message = messages[-1]['_id'] + 1
                self.refreshMessagesTimer.start(3000)

    def addMessage(self, author, message):
        message_container = QtWidgets.QWidget(self.chatContent)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(message_container.sizePolicy().hasHeightForWidth())
        message_container.setSizePolicy(sizePolicy)
        message_container.setMinimumSize(QtCore.QSize(0, 0))
        verticalLayout_6 = QtWidgets.QVBoxLayout(message_container)
        verticalLayout_6.setContentsMargins(0, -1, 0, -1)
        verticalLayout_6.setSpacing(2)
        nickname_label = QtWidgets.QLabel(message_container)
        nickname_label.setText(author)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        nickname_label.setFont(font)
        verticalLayout_6.addWidget(nickname_label)
        message_label = QtWidgets.QLabel(message_container)
        message_label.setText(message)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(message_label.sizePolicy().hasHeightForWidth())
        message_label.setSizePolicy(sizePolicy)
        message_label.setMinimumSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(10)
        message_label.setFont(font)
        message_label.setWordWrap(True)
        verticalLayout_6.addWidget(message_label, 0, QtCore.Qt.AlignTop)
        self.verticalLayout_4.addWidget(message_container)

    def sendMessage(self):
        message = self.messageField.toPlainText()
        self.web_handler.send_message_to_dialog(self.activeChat['_id'], message)
        self.messageField.clear()
        self.getNewMessages()

    def startConversation(self):
        self.start_conversation_window = StartConversationWindow(self.web_handler)
        self.start_conversation_window.show()

    def getNewMessages(self):
        messages = self.web_handler.get_new_dialog_messages(self.activeChat['_id'], self.last_message)
        print(messages)
        if len(messages) > 0:
            for message in messages:
                self.addMessage(message['sender'], message['content'])
            self.last_message = messages[-1]['_id'] + 1


class LoginRegisterWindow(QtWidgets.QMainWindow, LoginRegisterForm.Ui_LoginWindow):
    emitter = QtCore.pyqtSignal(str)

    def __init__(self, web_handler):
        super().__init__()
        self.setupUi(self)
        self.web_handler = web_handler
        self.signUpButton.clicked.connect(self.SignUp)
        self.signInButton.clicked.connect(self.SignIn)

    def SignUp(self):
        login = self.loginSignUpField.text()
        password = self.passwordSignUpField.text()
        status = self.web_handler.register(login, password)
        message_box = QtWidgets.QMessageBox()
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        message_box.setIcon(QtWidgets.QMessageBox.Information)
        if status:
            message_box.setWindowTitle("Registration successful")
            message_box.setText("Signed up successfully")
        else:
            message_box.setWindowTitle("Registration failed")
            message_box.setText("Failed to sign up")
        message_box.exec_()

    def SignIn(self):
        login = self.loginSignInField.text()
        password = self.passwordSignInField.text()
        status = self.web_handler.auth(login, password)
        if not status:
            message_box = QtWidgets.QMessageBox()
            message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            message_box.setIcon(QtWidgets.QMessageBox.Information)
            message_box.setWindowTitle("Signing in failed")
            message_box.setText("Failed to sign in")
            message_box.exec_()
        else:
            self.emitter.emit(login)


class Controller:
    def __init__(self):
        self.web_handler = WebHandler.Client()
        self.login = None
        self.messenger = None

    def show_login(self):
        self.login = LoginRegisterWindow(self.web_handler)
        self.login.emitter.connect(self.show_messenger)
        self.login.show()

    def show_messenger(self, login):
        self.messenger = MessengerWindow(self.web_handler, login)
        if self.login is not None:
            self.login.close()
        self.messenger.show()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    controller = Controller()
    controller.show_login()
    sys.exit(app.exec_())
