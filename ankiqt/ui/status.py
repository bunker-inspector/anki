# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import anki
import sys, time
from ankiqt import ui
from anki.hooks import addHook

class QClickableLabel(QLabel):
    url = "http://ichi2.net/anki/wiki/TheTimerAndShortQuestions"
    def mouseReleaseEvent(self, evt):
        QDesktopServices.openUrl(QUrl(self.url))

# Status bar
##########################################################################

class StatusView(object):
    "Manage the status bar as we transition through various states."

    warnTime = 10

    def __init__(self, parent):
        self.main = parent
        self.statusbar = parent.mainWin.statusbar
        self.shown = []
        self.hideBorders()
        self.setState("noDeck")
        self.timer = None
        self.timerFlashStart = 0
        self.thinkingTimer = QTimer(parent)
        self.thinkingTimer.start(1000)
        parent.connect(self.thinkingTimer, SIGNAL("timeout()"),
                       self.drawTimer)
        self.countTimer = QTimer(parent)
        self.countTimer.start(60000)
        parent.connect(self.countTimer, SIGNAL("timeout()"),
                       self.updateCount)
        addHook("showQuestion", self.flashTimer)

    # State control
    ##########################################################################

    def setState(self, state):
        "Change to STATE, and update the display."
        self.state = state
        if self.state == "initial":
            self.showDeckStatus()
        elif self.state == "noDeck":
            self.hideDeckStatus()
        elif self.state in ("showQuestion",
                            "deckFinished",
                            "deckEmpty",
                            "studyScreen"):
            self.redraw()

    # Setup and teardown
    ##########################################################################

    def vertSep(self):
        spacer = QFrame()
        spacer.setFrameStyle(QFrame.VLine)
        spacer.setFrameShadow(QFrame.Plain)
        return spacer

    def showDeckStatus(self):
        if self.shown:
            return
        progressBarSize = (50, 8)
        # small spacer
        self.initialSpace = QWidget()
        self.addWidget(self.initialSpace, 1)
        # remaining & eta
        self.remText = QLabel()
        self.addWidget(self.remText, 0)
        sep1 = self.vertSep()
        self.addWidget(sep1, 0)
        self.etaText = QLabel()
        self.etaText.setToolTip(_(
            "<h1>Estimated time</h1>"
            "This is how long it will take to complete the current mode "
            "at your current pace."))
        self.addWidget(self.etaText, 0)
        # progress&retention
        sep2 = self.vertSep()
        self.addWidget(sep2, 0)
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setMargin(0)
        self.progressBar = QProgressBar()
        self.progressBar.setFixedSize(*progressBarSize)
        self.progressBar.setMaximum(100)
        self.progressBar.setTextVisible(False)
        vbox.addWidget(self.progressBar, 0)
        self.retentionBar = QProgressBar()
        self.retentionBar.setFixedSize(*progressBarSize)
        self.retentionBar.setMaximum(100)
        self.retentionBar.setTextVisible(False)
        vbox.addWidget(self.retentionBar, 0)
        self.combinedBar = QWidget()
        self.combinedBar.setLayout(vbox)
        self.combinedBar.setFixedWidth(50)
        if QApplication.instance().style().objectName() != "plastique":
            self.plastiqueStyle = QStyleFactory.create("plastique")
            self.progressBar.setStyle(self.plastiqueStyle)
            self.retentionBar.setStyle(self.plastiqueStyle)
        self.addWidget(self.combinedBar, 0)
        # timer
        sep3 = self.vertSep()
        self.addWidget(sep3, 0)
        self.timer = QClickableLabel()
        self.timer.setText("00:00")
        self.addWidget(self.timer)
        self.redraw()
        if not self.main.config['showTimer']:
            self.timer.setShown(False)
        if not self.main.config['showProgress']:
            self.progressBar.hide()
            self.retentionBar.hide()
            self.timer.hide()
            self.etaText.hide()
            self.remText.hide()
            sep1.hide()
            sep2.hide()
            sep3.hide()

    def addWidget(self, w, stretch=0):
        self.statusbar.addWidget(w, stretch)
        self.shown.append(w)

    def hideDeckStatus(self):
        for w in self.shown:
            self.statusbar.removeWidget(w)
            w.setParent(None)
        self.shown = []

    def hideBorders(self):
        "Remove the ugly borders QT places on status bar widgets."
        self.statusbar.setStyleSheet("::item { border: 0; }")

    # Updating
    ##########################################################################

    def redraw(self):
        p = QPalette()
        stats = self.main.deck.getStats()
        remStr = _("Remaining: ")
        if self.state == "deckFinished":
            remStr += "<b>0</b>"
        elif self.state == "deckEmpty":
            remStr += "<b>0</b>"
        elif self.main.deck.reviewEarly:
            remStr += "<b>0</b>"
        else:
            # remaining string, bolded depending on current card
            if not self.main.currentCard:
                remStr += "%(failed1)s&nbsp;&nbsp;%(rev1)s&nbsp;&nbsp;%(new1)s"
            else:
                q = self.main.deck.queueForCard(self.main.currentCard)
                if q == "failed":
                    remStr += "<u>%(failed1)s</u>&nbsp;&nbsp;%(rev1)s&nbsp;&nbsp;%(new1)s"
                elif q == "rev":
                    remStr += "%(failed1)s&nbsp;&nbsp;<u>%(rev1)s</u>&nbsp;&nbsp;%(new1)s"
                else:
                    remStr += "%(failed1)s&nbsp;&nbsp;%(rev1)s&nbsp;&nbsp;<u>%(new1)s</u>"
        stats['failed1'] = '<font color=#990000>%s</font>' % stats['failed']
        stats['rev1'] = '<font color=#000000>%s</font>' % stats['rev']
        stats['new1'] = '<font color=#0000ff>%s</font>' % stats['new']
        self.remText.setText(remStr % stats)
        stats['spaced'] = self.main.deck.spacedCardCount()
        stats['new2'] = self.main.deck.newCount
        self.remText.setToolTip(_(
            "<h1>Remaining cards</h1>"
            "<p/>There are <b>%(failed)d</b> failed cards due soon.<br>"
            "There are <b>%(rev)d</b> cards awaiting review.<br>"
            "There are <b>%(new)d</b> new cards due today.<br><br>"
            "There are <b>%(new2)d</b> new cards in total.<br>"
            "There are <b>%(spaced)d</b> delayed cards.") % stats)
        # eta
        self.etaText.setText(_("ETA: <b>%(timeLeft)s</b>") % stats)
        # retention & progress bars
        p.setColor(QPalette.Base, QColor("black"))
        p.setColor(QPalette.Button, QColor("black"))
        self.setProgressColour(p, stats['gMatureYes%'])
        self.retentionBar.setPalette(p)
        self.retentionBar.setValue(stats['gMatureYes%'])
        self.setProgressColour(p, stats['dYesTotal%'])
        self.progressBar.setPalette(p)
        self.progressBar.setValue(stats['dYesTotal%'])
        # tooltips
        tip = "<h1>" + _("Performance") + "</h1>"
        tip += _("""The top bar shows your performance today. The bottom bar shows your<br>
performance on cards scheduled for 21 days or more. The bottom bar should<br>
generally be between 80-95%% - lower and you're forgetting mature cards<br>
too often, higher and you're spending too much time reviewing.""")
        tip += "<h2>" + _("Reviews today") + "</h2>"
        tip += "<b>" + _("Correct today: ") + anki.utils.fmtPercentage(stats['dYesTotal%'], point=1)
        tip += " (" + _("%(partOf)d of %(totalSum)d") % {'partOf' : stats['dYesTotal'], 'totalSum' : stats['dTotal'] } + ")</b><br>"
        tip += _("Average time per answer: ") + anki.utils.fmtTimeSpan(stats['dAverageTime'], point=2) +"<br>"
        tip += _("Total review time: ") + anki.utils.fmtTimeSpan(stats['dReviewTime'], point=2)
        tip += "<h2>" + _("All Reviews") + "</h2>"
        tip += "<b>" + _("Correct over a month: ") + anki.utils.fmtPercentage(stats['gMatureYes%'], point=1)
        tip += " (" + _("%(partOf)d of %(totalSum)d") % {'partOf' : stats['gMatureYes'], 'totalSum' : stats['gMatureTotal'] } + ")</b><br>"
        tip += _("Average time per answer: ") + anki.utils.fmtTimeSpan(stats['gAverageTime'], point=2) +"<br>"
        tip += _("Total review time: ") + anki.utils.fmtTimeSpan(stats['gReviewTime'], point=2) +"<br>"
        tip += _("Correct under a month: ") + anki.utils.fmtPercentage(stats['gYoungYes%'], point=1)
        tip += " (" + _("%(partOf)d of %(totalSum)d") % {'partOf' : stats['gYoungYes'], 'totalSum' : stats['gYoungTotal'] } + ")</b><br>"
        tip += _("Correct first time: ") + anki.utils.fmtPercentage(stats['gNewYes%'], point=1)
        tip += " (" + _("%(partOf)d of %(totalSum)d") % {'partOf' : stats['gNewYes'], 'totalSum' : stats['gNewTotal'] } + ")</b><br>"
        tip += _("Total correct: ") + anki.utils.fmtPercentage(stats['gYesTotal%'], point=1)
        tip += " (" + _("%(partOf)d of %(totalSum)d") % {'partOf' : stats['gYesTotal'], 'totalSum' : stats['gTotal'] } + ")</b><br>"
        self.combinedBar.setToolTip(tip)
        if self.main.config['showTimer']:
            self.drawTimer()
            self.timer.setToolTip(_("""
<h1>Time</h1>
Anki tracks how long you spend looking at a card.<br>
This time is used to calculate the ETA, but not used<br>
for scheduling.<br><br>
You should aim to answer each question within<br>
10 seconds. Click the timer to learn more."""))

    def setProgressColour(self, palette, perc):
        if perc == 0:
            palette.setColor(QPalette.Highlight, QColor("black"))
        elif perc < 50:
            palette.setColor(QPalette.Highlight, QColor("#ee0000"))
        elif perc < 65:
            palette.setColor(QPalette.Highlight, QColor("#ee7700"))
        elif perc < 75:
            palette.setColor(QPalette.Highlight, QColor("#eeee00"))
        else:
            palette.setColor(QPalette.Highlight, QColor("#00ee00"))

    def drawTimer(self):
        if not self.main.config['showTimer']:
            return
        if not self.timer:
            return
        if self.main.deck and self.main.state in ("showQuestion", "showAnswer"):
            if self.main.currentCard:
                if time.time() - self.timerFlashStart < 1:
                    return
                if not self.main.config['showCardTimer']:
                    return
                t = self.main.currentCard.thinkingTime()
                self.setTimer('%02d:%02d' % (t/60, t%60))
                return
        self.setTimer("00:00")

    def flashTimer(self):
        if not (self.main.deck.sessionStartTime and
                self.main.deck.sessionTimeLimit) or self.main.deck.reviewEarly:
            return
        t = time.time() - self.main.deck.sessionStartTime
        t = self.main.deck.sessionTimeLimit - t
        if t < 0:
            t = 0
        self.setTimer('<span style="color:#0000ff">%02d:%02d</span>' %
                           (t/60, t%60))
        self.timerFlashStart = time.time()

    def updateCount(self):
        if not self.main.deck:
            return
        if self.state in ("showQuestion", "showAnswer"):
            self.main.deck.checkDue()
            self.redraw()

    def setTimer(self, txt):
        self.timer.setText("<qt>" + txt + "&nbsp;")

