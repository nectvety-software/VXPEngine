"""Searchable offline documentation page for VXPEngine."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QUrl, Signal, QSize
from PySide6.QtGui import QDesktopServices, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from documentation_content import DocumentationTopic, build_topics, render_topic_page
from .icons import icon


class DocumentationPage(QWidget):
    """Complete offline manual with topic navigation and full-text filtering."""

    home_requested = Signal()

    def __init__(self, docs_directory: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("DocumentationPage")
        self.docs_directory = docs_directory
        self._topics = build_topics()
        self._topic_by_key = {topic.key: topic for topic in self._topics}
        self._visible_topics: list[DocumentationTopic] = []
        self._current_key = "overview"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_content(), 1)
        root.addWidget(self._build_footer())

        self.search_edit.installEventFilter(self)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self._populate_topic_list(self._topics)
        self.open_topic("overview")

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("DocsHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 14, 22, 14)
        layout.setSpacing(10)

        home_button = QToolButton()
        home_button.setObjectName("DocsHomeButton")
        home_button.setIcon(icon("fa5s.home"))
        home_button.setIconSize(QSize(16, 16))
        home_button.setToolTip("Về màn hình Home")
        home_button.clicked.connect(self.home_requested.emit)
        layout.addWidget(home_button)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Tài liệu VXPEngine")
        title.setObjectName("DocsTitle")
        subtitle = QLabel("Hướng dẫn offline cho Home, editor, build/run MRE VXP và core coremre")
        subtitle.setObjectName("DocsSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch()

        search_host = QFrame()
        search_host.setObjectName("DocsSearchHost")
        search_layout = QHBoxLayout(search_host)
        search_layout.setContentsMargins(10, 0, 8, 0)
        search_layout.setSpacing(7)
        search_icon = QLabel()
        search_icon.setPixmap(icon("fa5s.search", "#71829B").pixmap(15, 15))
        search_layout.addWidget(search_icon)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("DocsSearch")
        self.search_edit.setPlaceholderText("Tìm chủ đề, lệnh build, lỗi…  Ctrl+F")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_topics)
        self.search_edit.returnPressed.connect(self._open_first_search_result)
        search_layout.addWidget(self.search_edit, 1)
        search_host.setFixedWidth(390)
        layout.addWidget(search_host)

        self.open_markdown_button = QPushButton("Bản Markdown")
        self.open_markdown_button.setObjectName("DocsSecondaryButton")
        self.open_markdown_button.setIcon(icon("fa5s.file-alt"))
        self.open_markdown_button.clicked.connect(self._open_markdown_manual)
        layout.addWidget(self.open_markdown_button)
        return header

    def _build_content(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("DocsSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)

        nav = QWidget()
        nav.setObjectName("DocsNavigation")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(14, 16, 10, 16)
        nav_layout.setSpacing(8)

        nav_title = QLabel("NỘI DUNG")
        nav_title.setObjectName("DocsNavTitle")
        nav_layout.addWidget(nav_title)

        self.result_label = QLabel()
        self.result_label.setObjectName("DocsResultLabel")
        nav_layout.addWidget(self.result_label)

        self.topic_list = QListWidget()
        self.topic_list.setObjectName("DocsTopicList")
        self.topic_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.topic_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.topic_list.setSpacing(2)
        self.topic_list.currentItemChanged.connect(self._topic_selection_changed)
        nav_layout.addWidget(self.topic_list, 1)

        tips = QFrame()
        tips.setObjectName("DocsTipCard")
        tips_layout = QVBoxLayout(tips)
        tips_layout.setContentsMargins(12, 11, 12, 11)
        tips_layout.setSpacing(5)
        tip_head = QHBoxLayout()
        tip_icon = QLabel()
        tip_icon.setPixmap(icon("fa5s.lightbulb", "#EFCB6B").pixmap(15, 15))
        tip_head.addWidget(tip_icon)
        tip_title = QLabel("Mẹo tìm kiếm")
        tip_title.setObjectName("DocsTipTitle")
        tip_head.addWidget(tip_title)
        tip_head.addStretch()
        tips_layout.addLayout(tip_head)
        tip_text = QLabel("Thử: VXPEmu, build ARM, ký ứng dụng, coremre hoặc project.vxp.json")
        tip_text.setObjectName("DocsTipText")
        tip_text.setWordWrap(True)
        tips_layout.addWidget(tip_text)
        nav_layout.addWidget(tips)

        content_host = QWidget()
        content_host.setObjectName("DocsContentHost")
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("DocsContentToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(18, 8, 18, 8)
        toolbar_layout.setSpacing(6)

        self.back_button = QToolButton()
        self.back_button.setObjectName("DocsNavButton")
        self.back_button.setIcon(icon("fa5s.arrow-left"))
        self.back_button.setToolTip("Chủ đề trước")
        self.back_button.clicked.connect(lambda: self._step_topic(-1))
        toolbar_layout.addWidget(self.back_button)

        self.forward_button = QToolButton()
        self.forward_button.setObjectName("DocsNavButton")
        self.forward_button.setIcon(icon("fa5s.arrow-right"))
        self.forward_button.setToolTip("Chủ đề tiếp theo")
        self.forward_button.clicked.connect(lambda: self._step_topic(1))
        toolbar_layout.addWidget(self.forward_button)

        toolbar_layout.addSpacing(7)
        self.breadcrumb = QLabel("Tài liệu / Tổng quan")
        self.breadcrumb.setObjectName("DocsBreadcrumb")
        toolbar_layout.addWidget(self.breadcrumb, 1)

        top_button = QPushButton("Đầu trang")
        top_button.setObjectName("DocsToolbarLink")
        top_button.setIcon(icon("fa5s.arrow-up"))
        top_button.clicked.connect(lambda: self.browser.verticalScrollBar().setValue(0))
        toolbar_layout.addWidget(top_button)
        content_layout.addWidget(toolbar)

        self.browser = QTextBrowser()
        self.browser.setObjectName("DocsBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._open_link)
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.browser, 1)

        splitter.addWidget(nav)
        splitter.addWidget(content_host)
        splitter.setSizes([300, 1100])
        return splitter

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("DocsFooter")
        footer.setFixedHeight(30)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 0, 18, 0)
        status_icon = QLabel()
        status_icon.setPixmap(icon("fa5s.book-open", "#72A8FF").pixmap(13, 13))
        layout.addWidget(status_icon)
        self.status_label = QLabel("Tài liệu offline đã sẵn sàng")
        self.status_label.setObjectName("DocsStatus")
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.position_label = QLabel()
        self.position_label.setObjectName("DocsStatus")
        layout.addWidget(self.position_label)
        return footer

    def open_topic(self, key: str) -> None:
        topic = self._topic_by_key.get(key) or self._topic_by_key["overview"]
        self._current_key = topic.key
        self.browser.setHtml(render_topic_page(topic))
        self.browser.verticalScrollBar().setValue(0)
        self.breadcrumb.setText(f"Tài liệu / {topic.category} / {topic.title}")
        self.status_label.setText(topic.summary)

        for row in range(self.topic_list.count()):
            item = self.topic_list.item(row)
            if item.data(Qt.UserRole) == topic.key:
                if self.topic_list.currentRow() != row:
                    self.topic_list.blockSignals(True)
                    self.topic_list.setCurrentRow(row)
                    self.topic_list.blockSignals(False)
                break
        self._update_navigation_state()

    def _populate_topic_list(self, topics: list[DocumentationTopic]) -> None:
        selected_key = self._current_key
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        self._visible_topics = list(topics)
        previous_category = ""
        for topic in topics:
            if topic.category != previous_category:
                category_item = QListWidgetItem(topic.category.upper())
                category_item.setFlags(Qt.ItemFlag.NoItemFlags)
                category_item.setData(Qt.UserRole + 1, "category")
                category_item.setSizeHint(QSize(0, 30))
                self.topic_list.addItem(category_item)
                previous_category = topic.category

            item = QListWidgetItem(icon(topic.icon_name), topic.title)
            item.setData(Qt.UserRole, topic.key)
            item.setToolTip(topic.summary)
            item.setSizeHint(QSize(0, 40))
            self.topic_list.addItem(item)

        self.topic_list.blockSignals(False)
        self.result_label.setText(f"{len(topics)} chủ đề")

        for row in range(self.topic_list.count()):
            item = self.topic_list.item(row)
            if item.data(Qt.UserRole) == selected_key:
                self.topic_list.setCurrentRow(row)
                return
        if topics:
            self.open_topic(topics[0].key)

    def _filter_topics(self, text: str) -> None:
        query = " ".join(text.casefold().split())
        if not query:
            matches = self._topics
        else:
            tokens = query.split()
            matches = []
            for topic in self._topics:
                haystack = " ".join(
                    [topic.title, topic.category, topic.summary, *topic.keywords, topic.html]
                ).casefold()
                if all(token in haystack for token in tokens):
                    matches.append(topic)
        self._populate_topic_list(matches)
        if matches:
            self.result_label.setText(f"{len(matches)} kết quả")
        else:
            self.browser.setHtml(
                "<html><body style='background:#121722;color:#cbd5e1;font-family:Segoe UI;padding:34px'>"
                "<h1 style='color:#f3f6fb'>Không tìm thấy nội dung</h1>"
                "<p>Hãy thử từ khóa ngắn hơn như <b>VXPEmu</b>, <b>ký</b>, <b>coremre</b> hoặc <b>project</b>.</p>"
                "</body></html>"
            )
            self.result_label.setText("0 kết quả")
            self.status_label.setText("Không có chủ đề phù hợp")
            self.back_button.setEnabled(False)
            self.forward_button.setEnabled(False)

    def _topic_selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            return
        key = current.data(Qt.UserRole)
        if key:
            self.open_topic(str(key))

    def _open_first_search_result(self) -> None:
        if self._visible_topics:
            self.open_topic(self._visible_topics[0].key)
            self.browser.setFocus()

    def _step_topic(self, delta: int) -> None:
        if not self._visible_topics:
            return
        keys = [topic.key for topic in self._visible_topics]
        try:
            index = keys.index(self._current_key)
        except ValueError:
            index = 0
        new_index = min(max(index + delta, 0), len(keys) - 1)
        self.open_topic(keys[new_index])

    def _update_navigation_state(self) -> None:
        keys = [topic.key for topic in self._visible_topics]
        if self._current_key not in keys:
            self.back_button.setEnabled(False)
            self.forward_button.setEnabled(False)
            self.position_label.clear()
            return
        index = keys.index(self._current_key)
        self.back_button.setEnabled(index > 0)
        self.forward_button.setEnabled(index < len(keys) - 1)
        self.position_label.setText(f"Chủ đề {index + 1}/{len(keys)}")

    def _open_link(self, url: QUrl) -> None:
        if url.scheme() in {"http", "https"}:
            QDesktopServices.openUrl(url)
            return
        if url.hasFragment() and url.fragment() in self._topic_by_key:
            self.open_topic(url.fragment())

    def _open_markdown_manual(self) -> None:
        path = self.docs_directory / "VXPEngine_Manual.md"
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            self.status_label.setText(f"Đã mở: {path.name}")
        else:
            self.status_label.setText("Không tìm thấy bản Markdown trong thư mục docs")

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key_Down and self.topic_list.count():
                self.topic_list.setFocus()
                self.topic_list.setCurrentRow(max(0, self.topic_list.currentRow()))
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Find):
            self._focus_search()
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self.search_edit.text():
            self.search_edit.clear()
            event.accept()
            return
        super().keyPressEvent(event)
