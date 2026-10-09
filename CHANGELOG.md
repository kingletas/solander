# Changelog

## Unreleased

### A note's own link cannot drive the window

- **A link written in a note could run one of the window's actions.** Solander's own pages use addresses of a private scheme to ask the window to open a vault, search a tag, turn a book's page, reveal a folder, choose between notes of one name or open a file of the vault. A note could write such an address itself, as a link, an autolink or a reference, under any words it liked, and a click ran the action: with `open-recent`, the window left the vault the reader had chosen for another folder. None of it wrote a file, ran anything from a note or reached the network. Now a link a note writes with that scheme, in any spelling, has no address and is shown as unsupported. The links Solander writes itself are unchanged, and a note's ordinary link to another note still opens it.

### Prose kept in a block wraps, and any block can be copied

- **A letter kept in a text block ran off the right edge of the window**, one paragraph to a row, and could only be read by scrolling sideways. A fenced block tagged `text`, `txt` or `plain`, or with no language at all, now wraps to the page and keeps its own line breaks. A block with a language keeps its lines whole and scrolls, as code should. The PDF export already wrapped every block and still does.
- **Every fenced block has a Copy link in its corner**, shown while the pointer is over the block or the link has the keyboard's focus. It puts the block's text on the clipboard as the note has it: without the fence, without its language tag, and without the line break before the closing fence, so a letter with several paragraphs pastes as it was written.
- **Scripts in a note's page stay off.** The link is an address the window acts on, like a link to another note, and the window reads the block's text with a script of its own that is given a number and nothing else. A client that writes its own links gets no copy link unless it names where copies go.

### Moving quickly through notes renders only where you stop

- **Holding a key down the file tree rendered every note it passed**, each on its own thread, though only the last would be seen. A tab now has one render in flight and at most one waiting behind it: a request that arrives meanwhile replaces the waiting one, which is answered at once without being rendered. Ten notes asked for in a row render two, the first and the last, and `make smoke` checks it.

### A base opens in about a second, and the window keeps answering

- **A base over a large vault took seconds to render.** One whose formula follows every link, as a subject page does, built the same note's `file.` fields again for every link that reached it, and parsed every filter again for every note. The fields are now built once per index snapshot and each filter once, and a base's own filter is applied once for all its views: a subject base over 14,000 notes went from 13.3 seconds to 0.9, with the same rows.
- **The window froze while a base rendered.** A base is now rendered on a worker thread like a note, with the foot saying it is still opening, and `make smoke` holds one render for 1.5 seconds and fails if the window stalls for more than 250 ms meanwhile.
- The core change is in Slate's copy too.

### The smoke run no longer fails on which screen the window opens on

- **`make smoke` failed "the window opened at the saved width" whenever the window landed on a smaller or scaled monitor**, which the compositor clamps it to, so the same code passed from one terminal and failed from another. A window narrower than the saved size is now a `NOTE` with its width, and the board checks after it run at that width and say so. A window wider than the saved size still fails. **Solander not restoring the saved size still fails too**: a new check records the size Solander asks GTK for as it builds the window, which no compositor can change, and wants the saved 1872 by 1045.

### Search by property

- **Search takes Obsidian's property operator.** `[project:Garden Shed]` keeps the notes whose `project` property contains that value, or has an item that does when it's a list; `[status]` keeps the notes that have the property at all. Names and values are case-insensitive, a value may contain spaces, a wikilink such as `[[Some Note]]` is still searched as words, and it combines with words and the other operators like they combine with each other. Like `tag:`, it waits for the vault index, and says so if it isn't ready.

### A base renders its formulas, groups and limits

- **A base that used a formula said *not evaluated* instead of showing its rows.** `formulas` now evaluate for each note, and `formula.NAME` works in filters, columns, sorting and grouping, including one formula that names another. One that reaches itself says so rather than looping.
- **A view's `groupBy` is honoured**: its rows come in one group per value, in the group's direction, each headed with its count. A view's `limit` caps its rows, and the view says it was cut.
- **Bases' own expressions evaluate as Obsidian writes them**: `&&` and `||`, `list.filter(expr)` over `value`, `.length` on a list, `link.asFile()` to reach the note a link points to, `file.links` and `file.basename`, and a duration written as a string beside a date, as in `now() - "1d"`. Dataview's forms keep their meaning; a lambda passed to `filter` is read as before.
- The same change is in Slate's copy of the renderer.

### The PDF viewer stays above its note, and a page's block ids are capped

- **A PDF opened in its own window could fall behind the main window** and look as if it had never opened, since it had no parent. It is now transient for the main window, so it stays above it.
- **A page makes at most 1,000 block ids**, `READER_MAX_BLOCK_IDS_PER_PAGE`, as a backstop beside the other page limits. Markers past it still leave the page; their blocks just get no id, so a link to one lands at the top.

### A search clears when it should

- **Opening another vault left the first vault's search in the sidebar.** Its results, its count and the words in the box stayed, so one vault's note names showed inside another's window, and clicking one opened an error page naming a file the new vault does not have. Opening a vault now empties the box, the results and the status line, and a result that names a note the open vault lacks opens nothing.
- **Emptying the search box left its words marked in the open note.** The marks are part of the page, so they stayed until another note opened. Emptying the box, by its clear button, by deleting the text or with `Escape`, which now empties it, draws every marked tab again without them, at the same place in the note. The position is read and restored with the two scripts the window already runs in a page; no third is added.
- **An error page no longer carries search marks.** A search word that happened to be in the missing file's path was marked inside the error message.
- `make smoke` now also runs `scripts/search-smoke.py`, which drives the real window through both on two invented vaults, and fails six ways on the code before this change.

### A board fits a narrower window

- **In a window narrower than about 1500 pixels, a six-lane board ran off the right edge.** Its lanes stopped shrinking at 8rem, the last one was cut off behind a sideways scroll inside the page, and at that width a card's words broke in the middle. Lanes now wrap onto a second row once they would drop below 9rem, so every lane is in view and none is squeezed; in a wide window a board is one row, as before. The smoke run now measures each lane's edge against the board's and the page's own sideways scroll, where it compared whole-pixel scroll widths, which a lane laid out at a fractional width can miss by one.

### The read-only control says so

- **The header showed a lock and nothing else**, so what it meant was a guess until you hovered or clicked it. It now reads *Read-only* beside the lock, and a click still explains why and offers to show the source, open the note in your editor or reveal it in Files. When the header is short of room, the word shrinks before the other controls do.

### A mail link asks first

- **A `mailto` link opened the mail app the moment it was clicked.** Such a link can fill in a subject, a message and copies to other people, and a note from anyone can carry one, so opening it is now a question: it names who the email is to, the first three addresses and a count of the rest, and says what else the link fills in. Web links still open in the browser at once, and every other scheme still does nothing.

### The page follows the desktop's text size

- **Large Text made the menus bigger and left the note as it was.** GNOME's text scaling reaches an application only as GTK's font DPI, which WebKit does not read, so the reading page stayed at its standard size. The page now sizes its type by that DPI, and follows it when it changes while the window is open: at a scaling of 1.5, measured in the running window, the page's base size went from 16 to 24 pixels. Zoom still works on top of it, and an exported PDF keeps the standard size whatever the screen was set to.

### Tab gets past the file tree

- **Every row of the file tree was its own stop for `Tab`.** In a vault with a hundred notes at the top level, reaching the header or the page from the sidebar took a hundred presses. The tree is now one stop, with the arrow keys moving inside it, as a list is everywhere else on the desktop. The smoke run walks the whole `Tab` cycle from the page and back, the way the key does, and checks that it reaches every panel tab, the page and the tree once: 23 stops, where the old tree alone added 20 on the test vault.

### A screen reader can name what it lands on

- **Sidebar rows, search boxes and task checkboxes were announced by their role alone.** A result, a link, a bookmark, a tag or a heading in the sidebar was read as "list item", the three search boxes as a blank text field once their placeholder went, a checkbox in a note as "check box, not checked" with no task, and the pinned and recent list as its heading and first row run together. Each now has a name: a note row its title and path with the snippet as its description, a tag its count, a quick-list row whether it is pinned or recent, and a checkbox the text of its task. `make a11y` reads the running window over AT-SPI, the bus Orca reads, opens each sidebar panel as assistive technology would, and fails on any control on screen with no name or any button, tab or entry that cannot take keyboard focus. It does not press keys, so the order Tab takes is still unchecked.
- **Search says what it found.** The result count and messages such as "still indexing" were a line of text a screen reader never reached, since focus stays in the search box; they are now announced, the count that changes with every keystroke quietly.
- **An embedded image says what its author wrote for it.** `![[chart.png|Sales funnel]]` gave a screen reader the file name; the caption is its alt text now.
- **A folder's menu opens from the keyboard.** The Menu key or `Shift+F10` on a folder in the tree opens Read as Book and Hide Folder, which only a right-click reached before.
- **The local graph works without a pointer.** It was a picture you could only click. It now takes focus: the arrow keys move between the linked notes, with a ring showing where you are, Enter opens one, and a screen reader hears the whole neighbourhood as text and each note as you reach it.
- **A PDF's pages can be read by a screen reader.** They are drawn as pictures, so assistive technology found a document with nothing in it; each page now carries its number as its name and its text as its description, filled in a page at a time so a long document never holds the window.
- **The page shows where the keyboard is.** A focused link, fold or checkbox gets a solid ring in the theme's accent, where before it had only WebKit's default, which could be taken for a wikilink's dotted underline.
- **A Markdown link to a note is marked by more than its colour**, with the same dotted underline a wikilink has.

### The file tree sorts by date or type

- **The tree listed files by name and nothing else.** Preferences → Sort Files By now offers **Newest First**, which puts the note you last changed at the top of its folder, and **Type**, which groups notes, canvases, bases and attachments. Folders stay first and in name order whatever the choice, the tree keeps your expanded folders when it changes, and the choice is remembered.

### A long note no longer freezes the window

- **The window stopped answering while a note rendered.** The page was built on the thread that draws the window, so a 1 MB note held everything, from the sidebar to the close button, for several seconds. A note now renders on a worker thread with a renderer of its own, and the page is handed to the reading pane when it is ready. Measured in the running window while a 1 MB note rendered for about four seconds, the window's longest wait went from 3.2 seconds to under a tenth of a second.
- **A change to the vault could freeze the window for as long.** After every change, the watcher walked every folder of the vault on that same thread to find new ones, and while a note rendered alongside, each step of the walk waited its turn. The walk now runs on its own thread too.
- **A long note says it is opening.** A note that takes more than half a second to build shows a spinner and *Opening …* in the strip under the page, so the window no longer sits on the previous page with no sign anything is happening.
- **Leaving a long note before it appears stops its render.** It used to run to the end, slowing whatever you opened next; it now stops at its next step once the tab has asked for another page.
- **A change to the vault while a long note rendered could still pause the window for half a second.** The file tree and the panels updated while the note was being built, and every row they redrew waited its turn behind the render. They now catch up the moment the page arrives, and the render hands the window its turn five times as often. On a busy machine the longest pause while a 1 MB note rendered went from as much as 979 ms to under 70 ms, over five runs.

### A long note opens sooner

- **A note full of links rendered a third slower than it needed to.** Every `[[link]]` first looked for a file with the bare name, which can never be a note, and each miss resolved the whole path on disk, twice per link. The bare name is no longer tried, and a lookup that finds nothing now costs one check rather than a walk of the path. On a generated test note of 200 KB with about 3,800 links, rendering went from 0.89 to 0.63 seconds, and at 1 MB from 6.0 to 3.7 seconds. A note still renders while the window waits, so a very large one still pauses it.

### A restored session opens each note where you left it

- **Reopening Solander put every note back at the top.** The session remembered the vault, the note and the open tabs, but not how far down each one you had read. Closing the window now records, for every open note, how far down it was, as a share of the note's length rather than a pixel count, so a window of another size or zoom still lands on the same passage. The window reads that position through a script world of its own; the note's own scripts stay off.

### A link to a block lands on the block

- **`[[Note#^id]]` opens the note at the block, not at the top.** The link dropped the block id, and the page removed the `^id` marker without giving the block anything to scroll to, so every block link opened at the first line and `[[#^id]]` pointed at nothing. A block now carries its id: a paragraph or list item that ends in `^id`, and a table, list, quote or callout followed by a line holding only `^id`. That lone line used to show on the page as text; it is hidden now. A heading keeps its own anchor, and a note embedded in another gives its blocks no id, so no id appears twice on a page.

### Search finds what you meant

- **A note is found by its own name.** Full-text search read only note bodies, so a note called `Kubernetes` whose text never said the word was absent from a search for it. The name is now indexed and counts ten times a word in the body, so a note named for what you searched leads.
- **The word itself outranks longer words it begins.** Every word was matched only as a prefix, so `cat` put a note full of *catalogue* and *category* above one that says *cat*. Each word is now asked for whole and as a prefix, and the whole word wins.
- **A `path:`, `file:` or `tag:` filter no longer loses its note.** Filters ran after the index had already stopped at a thousand matches, so in a vault where a word is common a filtered search could come back empty. Filtered searches now see every match; on an 11,000-note test vault they answered in 80 to 220 ms.
- **Every word you searched is marked in the note you open, not only the first.** The page opens at the first one. The words are marked in the page before it is shown, since the reader runs no scripts, and they match as search does: case and accents aside, and at the start of a longer word. A marked hit is outlined, so it is not mistaken for a highlight in the note itself.
- **Quick-open prefers the note named by what you typed.** `plan` puts `People/Alan/Plan.md` above `Projects/Launch Plan.md`; `cafe` finds `Café.md`; and `md` no longer matches every note by its extension.

### The app's own notes describe the app

- **The shortcuts window left out keys the window answers to.** `F5` reloads, `Ctrl+=` zooms in, a book has its own page-turning keys, and a search result opens in a new tab on middle-click, `Ctrl+click` or right-click; none of these were listed, and the folder row pointed at a View menu that no longer exists. The list names all of them now. The keys the window binds live in one table beside that list, and a test fails when a bound key is missing from the list or a listed key is bound to nothing.
- **The welcome page was printing each recent vault's full path** under its name, the same leak the About dialog had. A card names its vault the way About and the recent-vaults menu do, and the smoke run fails if the welcome page contains the home directory.
- **The user guide, getting started, the walkthrough and the README described a window that had moved on.** They sent people to a View menu and a Note menu that are now Preferences and This note, put Theme before Mode, gave the rail a sepia it lost to Stone, put a breadcrumb on the page that now lives in the header bar, said a single note opens in its own folder when it opens in the vault that holds it, and said every link scheme but the web was refused when `mailto` opens your mail app. They now match the app, and the guide adds what it left out: `F5`, `Ctrl+=`, `F1`, the book keys, opening a search result in a new tab, Show Hidden Files and Markdown Files Only, and that search is case-insensitive with no phrase search. The software-centre screenshot pointed at an Atelier image that no longer exists and shows Stone now.


### A board fits the window

- **A Kanban board's lanes now share the page instead of each taking a fixed 260 pixels.** Six lanes needed about 1,620 pixels, so at the window size and zoom this reader is used at, the board ran off the side and was never in view at once. Lanes now shrink together down to 8rem each, card text wraps rather than widening its lane, and only a board too wide even then scrolls sideways. Measured in the running window at 1872 pixels wide, 140% zoom and the sidebar open: a six-lane board went from 735 CSS pixels of overflow to none, with each lane 159 CSS pixels wide.

### The file tree keeps your place

- **A change anywhere in the vault no longer collapses the file tree.** Every write the watcher saw emptied the tree and rebuilt its top level, so each expanded folder closed; with several writers in a vault that happened every few minutes. The tree now edits each folder it has listed in place, adding and removing only the rows that changed, so an open folder stays open and the row you were on stays where it was. Showing hidden files, Markdown only and hiding a folder keep your place the same way.

### The menu is a list, and About says what this reader promises

- **Twenty-odd entries in five sections became ten rows in four.** No headings: a heading is what a menu needs when it has stopped being a list you can read. Appearance, typography, preferences, this note, tabs and what to show are drill-downs; everything else is one row.
- **About is now about this run rather than about the app.** A card says what the reader does and, in bold, what it cannot do; under it, the vault it has open and the system details behind a button. The getting-started and user-guide pages left the menu for the place a person looks when they want to be shown around.
- **The About dialog was printing the vault's full path**, which says not only who the machine belongs to but how somebody files their own notes, and the same string is what **Copy system details** puts on the clipboard for pasting into an issue. The dialog names the vault the way the recent-vaults menu always has, and the copied details say whether a vault is open and how large it is and nothing else. The two messages that name a missing file abbreviate the home directory as well.

### The window is one surface, and it says where you are

- **The thirteen Archive themes never actually received the new chrome.** Their own `chrome_extra` is loaded after the shared structure, so everything it named silently won, and it named the rail's borders, its section labels and its selected row. Each theme kept the chrome it had before Stone: a gradient band with a thin bar and a near-white label where Stone states a chip with a 3px accent bar and the label in the accent. What is left there is the industrial scrollbar, which is the one part of it no shared token can say, and a test now fails if anything else joins it.
- **The rail's muted text was handed to the chrome unlifted.** Survivable while every rail was near-black; not once Stone's is a light surface. **Stone's own rail text measured 2.98:1**, and it was the only theme affected, so nothing else could have caught it. It is measured against the rail it sits on now, as the page's colours already were.
- **The rail is no longer a dark slab beside a light page.** Stone is one warm family (canvas, a slightly deeper rail and foot, raised surfaces above both), separated by hairlines rather than by value. Every colour the chrome names is now a token the theme defines; the white washes that used to draw a hover were invisible the moment the rail stopped being black.
- **The header bar says where the note lives.** The path to it, folders quiet and the note's own name in ink, with each folder a click into the tree. The page used to carry that line and no longer does, so it is stated once rather than twice, and a header with no room shortens the folders and keeps the name whole.
- **Search is a field you can see** rather than an icon you have to know, carrying the shortcut that also opens it.
- **The window has a foot.** What this reader may do and cannot do, how much is indexed, how long the open note is, and which theme is on with a dot in that theme's own colour. Everything in it is something the window already knew and never said. The lock in the header stays, because it opens the panel that explains the sentence the foot states.
- **Rows are chips, the rail's page switcher is a segmented control, and the tab you are on is a filled pill.** Radii are one scale throughout: rows and chips, then buttons and fields, then cards and callouts, then dialogs.
- **A callout is a tinted card** with its colour at the edge instead of a coloured bar down one side, and its title is set in the heading face. The icon stays: colour alone is still not allowed to mean anything.

### Stone: one design language, and every theme measured against it

- **Stone replaces Atelier as the house identity**, in a light and a dark version: warm neutral greys with the sepia taken out, one deep pine accent, and a sans in the chrome against a serif on the page. It is built from a palette like every other theme, so the last hand-written block of colours is gone from the app.
- **A palette now states which way its ground runs.** Four derived colours were measured from a dark ground and did the wrong thing on a light one: "brighter" made a title *less* prominent, and the code panel turned to mid-grey. Each reads the direction now.
- **Text on the solid accent is measured rather than assumed.** It used to be the palette's light end, which is wrong wherever the accent is bright: *Hazard* put text at 2.09:1 on its own accent and *Corrosion* at 2.28:1. The colour is chosen by contrast from the palette's own two ends, and the worst of the fifteen palettes is now 4.66:1.
- **A theme could reach paper and print the page black.** The palettes are generated after the print rules, so on equal specificity the screen colours won on source order, and printing an Archive note put the ink on its dark ground. Every generated palette is screen-only now, which is what the family's shared sheet already did.
- **Manrope and Literata are bundled**, because neither ships with a Linux desktop and a page that falls back to whatever is installed is a different design. They reach the page through `@font-face` on the reader's own route, not the vault's, where these files are not and must never have to be; and the window chrome through fontconfig, which cannot see inside a wheel. **Both were tested with fontconfig blind to the bundle**: the page is identical and the chrome falls back to Cantarell without moving the layout.
- **The Archive family keeps its colours and drops its second typographic system.** It was pinned to a serif for both display and body; it wears the house pairing now, and the rules it shares with every other theme moved to the base sheet, leaving it a third shorter and holding only what is its own: square tags, the rule under a title, code sunk into the ground, industrial scrollbars.

- **The theme is now chosen by looking at it.** The menu listed fourteen names; it shows each theme as a swatch drawn from that theme's own paper, ink and mark, with the one in force ticked. No picture is stored anywhere.

The Android port starts here. Neither of these changes the window; both are things the window's own design had made true only for the window.

- **Where a link points is now the client's decision, not the renderer's.** Every note link, asset, breadcrumb, tag, embed, backlink, canvas node, mind-map node and Dataview result was written with `reader:` or `vault:`, schemes only the GTK window can register, and which an Android or browser WebView cannot. A client passes the prefixes it wants and gets them everywhere; passing nothing gets the window's, so nothing changed for the client that was here first. **A client that says it has no window actions, with an empty prefix, gets a folder and a tag written as text rather than as a link nothing can follow.**
- **A link written as a path was being dropped by the sanitizer, silently.** It allowed a list of URL schemes, and a link a browser can follow is a path, so a page rendered for a path-based client came back with every wikilink stripped of its target and every image of its source. A path rooted at the page's own origin survives now; **`//` still does not, because a protocol-relative URL is another origin wearing a path's clothes.**
- **Measured against a large real vault rather than a fixture**: real notes, including a Dataview-heavy note, render with **zero** window schemes for a path client and unchanged output for the window.

- **The vault is now the only thing in the core that touches storage.** The renderer read a note's modified time by calling `stat` on the file itself, reaching around the `Vault` every other read goes through. The walk that builds the index now records each file's time and size as it goes, and the renderer and the indexer both read what it found. **Measured on a large real vault: building the index makes one fewer stat call per note, about 7.5% fewer in all.** No wall-clock claim is made; the difference was below the noise on the machine it was measured on.
- The reason is not the syscalls. **A storage backend that is not a POSIX filesystem now has one 210-line module to answer for**, which is what an Android or iOS port would need, and it was one `stat()` away from being untrue.

## 2.3.0 — 2026-09-05

Slate was forked out of this codebase, and several things fixed over there had never come back. These are the ones that are about reading a vault rather than about the runtime Slate became.

- **Every "last 30 days" Dataview query returned nothing.** `date(today)` writes the keyword bare, so the parser handed it back as a field name; evaluating it found no such property, and a comparison against nothing is silently false. There was no error and no empty-result message — the table simply had no rows in it, which reads as a vault with nothing recent in it. `today`, `now`, `yesterday` and `tomorrow` are answered as the dates they name, and only inside `date()`, so a note with a property called `today` still reads its own value.
- **`dateformat` lost Luxon's standalone month tokens.** `LLLL`, `LLL`, `LL` and `L` are what Luxon writes a month as when it is not part of a date, and each was passed through to `strftime` verbatim — so `yyyy-LL-dd` formatted as the literal text `LL` where the month belonged.
- **Search dropped everything in a folder Obsidian had been told to exclude.** Obsidian de-emphasises those files rather than hiding them, and a result only an archive holds is still the answer when nothing else matches. Full-text search now ranks them behind the rest, keeping the index's own order within each group; quick open still leaves them out, which is what Obsidian's own switcher does. A folder hidden *in this reader* is still hidden everywhere, because that one was asked for here.
- **A search result opened only where you clicked it.** Middle-click, `Ctrl+click` and right-click all open a note in a new tab from the file tree, and did nothing at all in the results list — the same sidebar behaving two ways depending on which half of it you were in.
- **The outline panel could not be resized.** It was sized by a fraction of the window with a ceiling, which is a layout the window decided and the reader could not argue with. It has a divider that drags, a floor of 200 px, and where it is left is remembered with the other pane preferences. The rail already worked this way.
- **Properties was a filled bar across the note before anyone opened it.** Closed, it is one quiet line with a disclosure arrow; the border and the surface arrive when it does.

Verifying those against the real window turned up three things wrong with the check that was meant to verify them.

- **A smoke run that stopped early printed `PASS`.** Every check is a GLib callback in one long chain, so an exception in any of them takes the rest with it — and a check that never ran reads exactly like a check that was never written. One run reported `PASS` on 38 of 120 checks. An exception in a callback is now recorded as a named failure, the run has to reach its last check to pass, and a watchdog ends a chain that has stopped so the verdict is still printed. The guard that was there covered only the case where *nothing* ran.
- **`make smoke` always exited 0.** The recipe cleaned up its fixture vault after the run with a `;`, which discarded the status, so the target reported success on a run that had said `RESULT: FAIL` on the line above.
- **The first two checks flapped.** They ran after a fixed 3.5-second delay, which is a bet on how loaded the machine is; on a busy one the landing note had not rendered and *a note is shown* failed on a tree that was fine. The run waits for the note to be on screen, keeping the old delay as a floor so it can only ever wait longer, and checks anyway past a bound rather than hanging.

- **Moving a tag no longer fails the release after building everything.** The publish step created the GitHub release, and creating one that already exists is an error — so re-tagging 2.2.4 built both packages, install-tested each of them, and then discarded the lot on the last line. An existing release now has its notes updated and its assets replaced instead.

## 2.2.4 — 2026-09-04

- **A note that opens with a heading is now called that.** A vault of folder indexes was a vault of notes called README, with the real name printed again a line below. The leading heading becomes the title and leaves the body, so it is shown once; a note with no leading heading keeps its filename.
- **The tags in a note's metadata line each had a separator drawn inside them.** The dot between items was the chip's own pseudo-element, and a chip has a border, so `· #index` rendered as one chip. Facts and tags are now two runs that separate differently — and at most five tags are shown before the count.
- **The outline indented every note by one step even when it had no hierarchy.** A note whose headings are all at one level was drawn as though there were a level above it that nothing was at; it now indents relative to the shallowest heading the note actually has.

- **Quick-open could rank a name that only contains the letters of `brief`, scattered across two words, above a filename containing the word `brief`, for the query `brief`.** No weighting fixes that: a run of the right letters in the wrong word is a different *kind* of match from the word itself, and a person typing a word means the word. Matches are classed first and scored second, so a literal match can no longer be outscored by a scattered one, and a filename that is a bare number, such as a date written without separators, is found instead of buried under every note that mentions that date.
- **Opening a note from a file manager made its own folder the vault.** A note three folders deep opened a vault of three files, with every link out of it broken; it looked like the app not working unless the note happened to sit at the vault root. The nearest folder above it carrying an `.obsidian` directory is the vault now, and the walk stops at your home directory so a stray marker above it cannot swallow everything.

- **Opening a vault for the first time is about twice as fast.** On a large real vault the first index build went from **30.9 to 14.7 seconds**, and rendering a note is **25% faster** (16.8 ms to 12.6 ms on average). Two causes: frontmatter was parsed by PyYAML's pure-Python scanner, which dominated the index build because almost every note has a properties block; and resolving a wikilink asked the filesystem whether each candidate path existed, one syscall per candidate, when the vault index already held the answer. Frontmatter now parses through LibYAML where it is available, and a path found by walking the vault is answered from the index.
- **The alias refusal is enforced against the parser that actually runs.** Aliases were refused by overriding `compose_node`, which LibYAML never calls — it composes in C — so the faster loader would have silently accepted the YAML bomb the bound exists to stop. Aliases are now refused by scanning the parser's own event stream before anything is composed, and a fast test covers the refusal directly, because the bomb test detects its loss by hanging rather than by failing.
- **A symlink pointing outside the vault no longer appears in the file index.** Reading one was already refused, and so was resolving a link to one, but the walk still listed it — so it showed up in the file tree and in search results. It is now dropped while indexing, which is also what lets a path found in the index be trusted without re-checking containment. Symlinks that stay inside the vault are unaffected.

- **The version is declared in one place.** It was five: the package, `pyproject.toml`, the install command in each of two documents, and the AppStream entry a software centre reads — plus the changelog heading, and the tag. Two releases were shipped wrong by it, 2.2.1 announcing itself as 2.2.0 and 2.2.4 tagged with its notes still headed Unreleased. `__version__` is now the only literal: `pyproject.toml` reads it through hatchling, everything outside Python asks `packaging/version.sh`, and the documented install commands take whichever bundle you downloaded rather than naming a version. `make release VERSION=` promotes the changelog section and the software centre entry together, and the test suite refuses a version missing either — so a mismatch now fails in the working tree instead of nine seconds into a release that has already been tagged.

## 2.2.3 — 2026-09-02

- **Frontmatter works in notes with Windows line endings.** A leading YAML block delimited with CRLF is now recognized like the same block with Unix line endings, so its title, tags, CSS classes and plugin metadata no longer appear as Markdown body text. Contributed by Mark Hodge.
- **Every continuous-integration action moved to its current major version**, each still pinned to a commit. The artifact actions are used only when publishing a release, so this is the first release to exercise them.

## 2.2.2 — 2026-09-02

Two defects found by installing the published package rather than trusting the build.

- **The Flatpak refused to start.** The check that decides whether WebKit's sandbox can run probes `bwrap --unshare-user`, and inside Flatpak that probe always fails — the process is already in Flatpak's own user namespace and nesting another is refused — **while WebKit's sandbox works perfectly, because Flatpak is the confinement**. So the one install route documented as needing no setup was the only one that would not open, and the AppArmor fix it printed could never have changed the result. The probe is skipped inside Flatpak, and two tests hold the line: one that it is skipped there, one that it still runs everywhere else.
- **The application reported the wrong version.** `__version__` in the package and `version` in `pyproject.toml` are two literals, and only the second is what the release job checks against the tag and the changelog — so 2.2.1 shipped announcing itself as 2.2.0. A test now asserts the two agree, and both workflows assert that the installed package prints the version they built.
- **CI now launches what it builds.** The Flatpak job checked `--version` and rendered a page in-process; neither goes through the startup path, which is why a Flatpak that could not start passed every gate. It now asserts the sandbox check answers correctly inside the bundle.


## 2.2.1 — 2026-09-02

A documentation and metadata pass after the first release.

- **The AppStream metainfo did not validate**, which matters because it is the file a software centre reads and Flathub refuses a submission whose metainfo fails. It had no homepage URL, used a deprecated developer tag, and carried **no screenshots, categories or keywords at all** — so the app would have appeared in GNOME Software as a name and a paragraph. It now carries the five project URLs, two screenshots, the categories and keywords the desktop entry already declared, and branding colours taken from the app's own icon.
- **Nothing validated either the desktop entry or the metainfo.** `make check` now runs both, and CI installs the validators so the check always runs there rather than degrading to a skip. That is how the metainfo came to be invalid without anyone knowing.
- **Getting started only knew how to build from source.** It walked a new reader through installing `uv`, cloning the repository and the one-time sandbox step — while a released Flatpak skips all of it. It now leads with the two packaged installs and marks the sandbox step as source-only.
- **The Flatpak instructions could not be followed.** The bundle is 3 MB and does not contain the GNOME 50 runtime it needs, so installing it requires a remote that provides the runtime. Neither document said so. Both now do, along with the note that a Flatpak install puts no `solander` on the `PATH`.
- **Every GitHub Action is pinned to a commit SHA** rather than a moving major tag, so a compromised or rewritten tag cannot change what runs in CI. A pinned SHA never moves, which is also the risk — a Dependabot configuration now opens a pull request when a pinned action releases a new version, so the pins do not quietly freeze this repository on the day they were written.
- **The documentation is checked the way the code is.** A new test resolves every relative link and heading anchor across the six documents, asserts that package filenames in the docs match the version in `pyproject.toml`, and asserts that the theme counts written in prose match the registry. It caught a link broken by renaming a heading in this same pass. The changelog is exempt from the last two: it records what was true at each release.


## 2.2.0 — 2026-09-02

Tagging a release now builds and publishes the packages.

- **Debian package.** `packaging/deb/build.sh` produces an `Architecture: all` deb — every dependency is pure Python — that vendors the app and its libraries into `/usr/lib/solander`, declares the GObject bindings as apt dependencies, and **ships the AppArmor profile**, parsed by the postinst. A deb user has no sandbox step at all.
- **Flatpak.** The manifest is real now rather than a starting point, and **built, bundled, installed and run before shipping**: the GNOME 50 runtime, every dependency pinned by sha256 because flatpak-builder builds with the network off, and no network permission granted at runtime. Three things were wrong on the way and each is worth knowing: the SDK has no `hatchling`, so `--no-build-isolation` could not build the app until the backend was pinned too; `pygments` existed in the SDK and was therefore **skipped**, which would have shipped a bundle missing it, so every dependency is now installed with `--ignore-installed`; and **GNOME 48 is end-of-life**, which for a WebKit application means an unpatched browser engine. `PyYAML` is the one dependency whose wheel is tied to the runtime's Python ABI, and the manifest says so. Inside Flatpak there is no AppArmor step either — the sandbox WebKit needs comes from Flatpak's own bubblewrap.
- **`Release` workflow.** Push a `v*` tag and it builds both, **installs each one and checks what it put on the system**, then publishes them on a GitHub Release whose body is that version's changelog section. It refuses to start when the tag, `pyproject.toml` and the changelog disagree.
- **CI builds the packages too**, so a tag is never the first time the packaging runs: the deb on every change, the flatpak on pushes to main. Both go further than building — each installs its package and **renders a page inside it**, because `--version` imports almost nothing and would have passed with a dependency missing.
- **The profile names the right thing for each install shape.** From source it names the private interpreter in the virtualenv; from a system package it names `/usr/bin/solander`, because naming `/usr/bin/python3` would grant user namespaces to every Python process on the machine. That is the shape Ubuntu's own profiles for packaged Python applications use.
- `make deb`, `make flatpak` and `make notes VERSION=x.y.z` run the same scripts CI runs.
- **The unit suite no longer needs GTK to run, and a test now says so.** One test reached into the window layer for a function that only builds a string; it passed on any machine with the GObject bindings installed and failed on a clean one, which is what CI is. The string-builder moved beside the profile it wraps, and two checks hold the line: the core and the CLI are imported in a fresh interpreter with `gi` blocked, and no unit test may import `solander.gui`. Both were proven against a deliberate breach.
- **The packaging scripts were untracked when first written**, for the third time from the same cause: this machine's global `core.excludesFile` refuses `*.sh`, and the negation added when the installer hit it was scoped to `scripts/` alone. The release workflow would have failed on a file that had never been pushed. The negation now covers the whole repository, and every shell script in the tree is confirmed tracked.

## 2.1.1 — 2026-09-02

Documentation pass before the first public push.

- **The name is explained**, in the README and in the About dialog: a solander is the clamshell box an archive keeps its documents in — open it to look at something, close it, and nothing has changed.
- **Screenshots**, of both the default theme and the Archive family.
- **CONTRIBUTING.md**: the three promises a change is measured against, how the virtualenv has to be built for the GI bindings to be visible, what the smoke run covers, and where code belongs.
- The About dialog links the project and its issue tracker.
- Fixed the rename's one grammar slip — *"puts an `solander` launcher"* — in the README and getting started.

## 2.1.0 — 2026-09-02

Two flags for the sandbox, the same two in every app here.

- **`--sandbox`** prints the AppArmor profile this installation needs and nothing else, so it pipes: `solander --sandbox | sudo tee /etc/apparmor.d/solander`. It replaces the documented recipe of `sed`-ing the profile out of the app's own stderr, which only worked while the app happened to be failing.
- **`--sandbox-status`** reports the profile, the interpreter, the AppArmor label and whether bubblewrap can actually unshare — and names the two failures that look identical from the outside: a profile naming a **shared interpreter** (which would grant user namespaces to every process using it), and a profile that is installed but **did not attach** to this process. Exits non-zero while anything is wrong.

## 2.0.3 — 2026-09-02

- **The mark fills its cell.** Enlarging the standalone silhouette was not enough: a plate on a plinth simply carries less ink than the near-full-bleed shapes it sits beside, so it kept reading as half-size in a dock. The sigil now sits on its own tile — **88% coverage against a neighbour's 82%** — with the record, the cut, the seal and the ledge inside it. The identity is unchanged, and it still re-tints per theme. Compared against a square and a round neighbour at 96, 64, 48, 32 and 24px, in five themes, and in silhouette.

## 2.0.2 — 2026-09-02

- **The mark fills its canvas.** The sigil covered 38% of the 128px square, so beside near-full-bleed neighbours it read as half-size in a dock. The geometry is unchanged in kind — plate, cut, seal, plinth — and now covers about 75%: a wider plate, a full-width plinth, and a larger seal. Checked against a square and a round neighbour at 64, 48, 40, 32 and 24px.

## 2.0.1 — 2026-09-02

The window had never carried its own icon, and the rename made it visible.

- **The process now identifies itself as the app id.** Wayland takes a toplevel's app id from the program name, and the desktop matches a window to its `.desktop` file — and therefore to its icon — by exactly that. Launched as `python -m solander.cli`, the program name was `cli.py`, which matches nothing, so the window and its dock entry drew a placeholder. `GLib.set_prgname(APP_ID)` fixes it, and a smoke check asserts it. **This was true under the old name too; the rename only made it noticeable.**
- **The installer refreshes the icon theme cache.** A stale `icon-theme.cache` takes precedence over the directory it sits in, so an icon installed after the cache was written is invisible — which is exactly what happened: the cache still listed `com.kingletas.ObsidianReader` and did not list `com.kingletas.Solander`. `install.sh` and `uninstall.sh` now rebuild the cache, or delete it when the theme has no index file.
- A unit test asserts the desktop entry, the metainfo and the icon filename all agree with `APP_ID`, so a future rename cannot half-land.

## 2.0.0 — 2026-09-02

**Obsidian Reader is now Solander.**

A solander is the clamshell box an archive keeps its documents in — which is the job: present the record, and leave it exactly as it was found. The old name described the first version of the app and had stopped describing this one, and it borrowed a trademark it has no claim to. Obsidian compatibility is unchanged and total; it is now a property rather than the product's name.

- **New identity**: the app is `Solander`, the command is `solander`, the app id is `com.kingletas.Solander`, and the Python package is `solander`. The desktop entry keeps `GenericName=Markdown Reader` and `Keywords=…obsidian…`, so searching your applications for "obsidian" or "reader" still finds it.
- **Your state comes with you.** The first launch adopts `~/.config/obsidian-reader` and `~/.cache/obsidian-reader` under the new names — recent vaults, theme, pinned notes, book progress and every vault's index — so the rename is not a reset. Adoption only happens when the new directory does not exist yet, so it can never overwrite live state.
- **Environment overrides renamed** to match: `SOLANDER_HOME`, `SOLANDER_SKIP_SANDBOX_CHECK`, `SOLANDER_FORCE_SETUP`. The `READER_MAX_*` bounds keep their names.
- **The AppArmor profile is now `/etc/apparmor.d/solander`.** It names the interpreter by path, so moving the checkout requires reinstalling it — `solander` prints the profile rendered for your installation, and the old `/etc/apparmor.d/obsidian-reader` can be deleted.
- Nothing about the reading surface changed: same fourteen themes, same mark, same renderers.

**Two defects in the install path, found while moving the checkout:**

- **`scripts/install.sh` and `scripts/uninstall.sh` were never in the repository.** `~/.gitignore` is `core.excludesFile` for every repo on this machine and it excludes `*.sh`, so git had silently refused both files since the first commit — a clone had no installer, and `make install` would have failed on a `No such file or directory` for a file the README tells you to run. A repo-local `!scripts/*.sh` negation overrides it, and both are committed now.
- **`make install` built a virtualenv the app could not start from.** Where no `.venv` existed yet, `uv sync` created one on uv's own interpreter, without system site packages — so `import gi` failed and the GTK bindings were invisible. It now creates the venv against the system Python the way `make sync` does, and **refuses to report success if the venv cannot import `gi`**, naming the apt packages to install.

## 1.14.0 — 2026-09-02

Blood Record became a family of thirteen.

- **The Archive family.** *Blood Record*, *Ember Archive*, *Blackout*, *Corrosion*, *Bruise*, *Drowned*, *Sepulcher*, *Cold Iron*, *Hazard*, *Velvet Knife*, *Ash*, *Null* and *Black Blood* — thirteen dark themes sharing one design language and one stylesheet. Appearance → Theme, now grouped by family.
- **A theme is a palette.** Sixteen colours in `core/palettes.py` and no rules: the page tokens, the whole GTK chrome and the syntax palette are all generated from them. Adding the fourteenth is one entry.
- **Semantics hold across the family**: danger, warning, verified and information mean the same thing in every theme, and a broken link takes the theme's danger colour rather than its accent.
- **Every colour that carries words is measured.** A solver lifts any text colour that misses WCAG AA on the ground it sits on, and the suite asserts it for all thirteen themes — body text, muted text, links, code, callout titles and the rail's labels — against the page, the panels, and the code ground. **This caught three failures in Blood Record as shipped**: its link (4.44), its hot red as a broken-link marker (3.88) and its rail labels (2.48). Its surfaces and accent are unchanged; only the colours carrying text moved.
- Atelier is untouched.

## 1.13.0 — 2026-09-02

The app mark is a sealed record now, not a book with a padlock.

- **One sigil, two identities.** A bound archival plate standing on a plinth, with a diamond **cut through the plate** and a seal set into the cut. The geometry is identical in both themes; only three fills change — lapis board and gold seal in Atelier, dried blood and arterial red in Blood Record — and the welcome page re-tints them in CSS, so the mark follows the theme without a second file.
- **Built to survive 16px**: no gradients, filters, masks, rasters, text or external references; three paths, integer coordinates, the seal cut with `fill-rule="evenodd"` rather than a mask. Checked at 128, 64, 48, 32, 24 and 16, in silhouette, and reversed.
- The padlock, the ruled text lines and the gradients are gone — they made it a generic document app with security software bolted on.

## 1.12.0 — 2026-09-02

A second theme, and a place for the next one.

- **Blood Record.** A dark archive rather than a notebook: charcoal and bone, oxidized copper for what is important, dried blood for the structure, and one hot red held back for what actually matters — a critical callout, a link that resolves to nothing, the document currently under your hand. It dresses the whole application, rail and menus included, and brings its own syntax palette. Appearance → Theme.
- **The original theme is untouched.** Atelier keeps its parchment, its gold and its lapis links, byte for byte; the new theme is layered over the dark palette rather than replacing anything.
- **A theme is a palette now, not a rewrite.** Page tokens, chrome colors and syntax colors live in one registry, and the chrome structure names those colors instead of hardcoding them — so a further theme is a palette and nothing else. The sidebar's CSS class stopped being named after one theme.
- **A dark-only theme greys out the light/dark choice** rather than accepting it and ignoring it; the mode you had comes back when you return to Atelier.
- Print is untouched: the theme is screen-only, so PDF export still renders on white through the same print stylesheet.

## 1.11.1 — 2026-09-02

- **The place indicator can no longer overlap the page.** It sits in its own strip below the page instead of floating over the last line.
- **Pages keep a book's measure.** The printed page is capped at a focused width (~880px) regardless of screen size, centered on the desk — on a large monitor the book is a book, not a wall.
- **The desk is opaque.** The paged view paints the desk color behind the page, so nothing shows through around it, and showing pages re-asserts reading mode.

## 1.11.0 — 2026-09-02

Book mode turns pages now, not chapters.

- **Real pagination, no scrolling.** Opening a book prints each chapter through WebKit's own print pipeline at exactly the reading area's size — true page breaks with line integrity, no JavaScript anywhere — and Poppler draws the pages one at a time. `N`/`P`, arrows, Space and PageUp/Down turn pages with the slide animation; clicking the right side of a page turns forward, the left third back.
- **Chapters roll over at their covers.** The last page turns into the next chapter; turning back past a first page lands on the previous chapter's *last* page. A quiet indicator at the page's foot reads *chapter 4 of 37 · page 3 of 12*.
- Book pages print their own colors: the chapter's stylesheet background (a manuscript's parchment included) survives into the printed page via print-color-adjust, and the book-nav footer stays out of print — navigation is keys and clicks.
- Printed chapters are cached for the session, so returning to a chapter is instant; without Poppler, book mode falls back to 1.10.0's chapter-at-a-time behavior.

## 1.10.0 — 2026-09-02

Book mode: the reader as a lectern for the manuscripts themselves.

- **Read as Book** (right-click a folder of chapters): reading mode opens on your last-read chapter, every page is the chapter alone — title, prose, and the way onward — and each chapter ends with its neighbors by name plus your place in the book. `N`/`P` turn chapters; progress is remembered per book; `Esc` closes the book.
- **Pages turn like pages.** Changing chapters slides the old page away over the incoming one — a GTK-side animation on a snapshot of the outgoing page, so the no-JavaScript rule is untouched.
- **The book wears its own design.** Chapters with `cssclasses` take their vault snippet in full: `@font-face` now survives the snippet sanitizer when (and only when) its src is a font in the vault's own `.obsidian/fonts`, served over the vault scheme with `font-src` opened to exactly that. Rendered pages also carry Obsidian's `.markdown-preview-section` structure, so snippets written against Obsidian's preview DOM — drop caps included — apply verbatim. The desk behind the page is tinted from the book's declared paper color.
- Books without a stylesheet get a built-in treatment: justified serif at reading size, a drop cap, centered chapter titles, asterism scene breaks.

## 1.9.0 — 2026-09-02

Mermaid diagrams render — and note content still never executes.

- **Flowcharts, sequence diagrams, and pies draw as static SVG**, laid out by a pure-Python engine: node shapes (rectangles, rounded, stadium, circle, diamond, hexagon, cylinder, subroutine, flag), dotted/thick/bidirectional edges with labels, chained statements, subgraphs with titles, `style`/`classDef`/`:::class` stroke styling, quoted labels spanning lines, `<br/>` line breaks; lifelines, dashed replies, self-messages, notes and loop/alt bands; pie slices with a legend. Measured against a large real vault: **97.8% of its blocks render**, and the rest are gantt/state/timeline/xychart/er, which show as labeled source naming the kind.
- Layout does the unglamorous work: ranks ignore cycle-closing edges, gaps widen for the labels that cross them, co-located labels stagger, reverse edge pairs bow apart, and labels layer above every line.
- The sanitizer gained a scoped SVG allowlist (geometry and presentation attributes only, colors and paths pattern-checked); mermaid source is parsed as data and mermaid.js is never involved, so the no-JavaScript promise holds unchanged.
- `READER_MAX_DIAGRAM_NODES` (400) bounds hostile input like every other renderer.

## 1.8.1 — 2026-09-02

- **The outline lives in the right panel only.** The sidebar's Outline page shipped with a serious defect, and rather than patching around it the page is removed — along with the Outline Position option and the side-switching it required. `F8` and the header button toggle the right panel, which keeps its close button, its styling, and its memory. A smoke check now asserts the rail carries no outline page.

## 1.8.0 — 2026-09-02

One outline, on the side you choose.

- **The outline never shows in two places.** Opening the right panel switches the rail off its Outline page; picking the rail's Outline page collapses the panel. View → Outline Position chooses which side `F8` and the header button open — Left Sidebar or Right Panel — and changing it moves an open outline across immediately.
- **The rail outline dresses for the rail.** A gold OUTLINE heading, muted entries with a visible hierarchy — top-level headings bright and semibold, deeper levels dimmer and smaller — and gold on hover, instead of the plain text dump it launched as. The right panel picks up the same level hierarchy in its serif.

## 1.7.0 — 2026-09-02

Sidebar structure, on request.

- **Pinned & recent is a section now, and collapsible.** A disclosure on its label folds it away (remembered), a separator and a FOLDERS label separate it from the tree — no more two lists running into each other.
- **The outline can live in the rail too.** A seventh sidebar page shows the current note's headings on the left, mirroring the right panel — use whichever side suits the note, or both.
- **The tags and graph icons are visible again.** The custom bundled icons were never treated as symbolic by GTK, so they drew their baked dark gray — invisible on the dark rail. Replaced with the theme's own recolorable icons (a smoke check now asserts both stay symbolic).

## 1.6.1 — 2026-09-02

- **The outline panel matches the interface now.** It sits on a warm card surface in the canvas family, its label in the identity's gold, its entries in muted serif that answer in lapis on hover — instead of the stock widget styling it launched with.

## 1.6.0 — 2026-09-02

The two-surface release: depth instead of tint.

- **The sidebar is a rail now.** A deep sepia surface running the full height of the window — the vault's name in gold small caps at its top, the section switcher under it, gold selection with an accent bar, tinted icons, dark-styled search fields, and the note/tag count at its foot. Against the parchment canvas the window finally has fore- and background instead of one beige sheet. It still resizes by its divider and still hides with F9.
- **The header belongs to the content.** It sits flat on the canvas beside the rail rather than spanning the window as a third tint.
- **The note title never doubles and never goes missing.** When a note opens with an H1 repeating its filename, the body's copy yields to the header title — so every note starts the same way: breadcrumb, serif title with its gold rule, metadata line. (Previously the header title was suppressed instead, leaving the metadata line floating alone above the properties panel.)
- The local-graph pane draws in the identity's gold, and the outline panel keeps its place on the content side.

## 1.5.0 — 2026-09-02

The UX pass: every surface gets an obvious control, and the one element without one is gone.

- **The outline is a real panel now.** The floating "On this page" rail — which overlapped content and had no way to close it — is removed. In its place: a native outline panel docked on the right, with a visible toggle in the header (`F8`), its own close button, animated reveal, heading hierarchy, an empty state, and a memory of whether you keep it open. It replaces the cramped header popover too.
- **The header bar says what it does.** A sidebar toggle now sits at the far left (`F9` still works); the right side is search, outline, menu. The wide Read-only pill shrinks to a quiet lock icon — the explanation and its next actions (view source, open in editor, reveal in Files) are still one click away.
- Reading mode hides the outline panel with everything else and restores it on exit; the outline state, like every other panel, persists across sessions.
- View → Note Context now lists exactly the three elements that live in the page: Title & Breadcrumb, Metadata Line, Linked Mentions.

## 1.4.0 — 2026-09-02

The atelier redesign: one visual identity across the whole app, and every piece of it under the reader's control.

- **A manuscript identity.** The reading canvas wears parchment and sepia ink with lapis links and gold ornament by day, a candlelit nocturne by night. Serif display type carries titles and headings, the note title gets a short gold rule, section breaks render as a fleuron, blockquotes open with a proper quotation mark, and the app icon is retinted to match.
- **The chrome wears the same palettes.** The GTK window — sidebar, header bar, popovers, dialogs — is themed to the exact colors of the reading canvas in both light and dark, so the window and the page read as one surface instead of a browser in a frame. The header title is set in the display serif; a system light/dark flip re-tints the chrome and re-renders every open page together.
- **A real welcome page.** The app opens on a frontispiece: the mark, the name, two action cards, in-app documentation links, and recent vaults as cards — not a bare paragraph.
- **Note context is a choice, not a fixture.** View → Note Context toggles Title & Breadcrumb, the Metadata Line, the On This Page rail, and Linked Mentions individually — persisted, applied to every tab at once. The rail can now simply be switched off.
- Syntax-highlighted code blocks sit on the page's own surface in both themes (Pygments used to force its own panel color), and callout tints are softened to sit quietly on the warm background.

## 1.3.0 — 2026-09-02

The look-and-feel release: editorial rather than dashboard-like, with context before content.

- **Every note opens with its context.** A clickable breadcrumb above the title (each ancestor reveals its folder in the tree), an inline title when the body does not start with one, and a quiet metadata line — updated date, word count, read time on longer notes, and clickable tag chips that run a tag search.
- **An "On this page" rail** lists the note's headings beside the text on windows wide enough to hold it — fixed, scrollable, and gone in print. It steps aside when the line width is set to Wide or Full.
- **Linked mentions follow the content.** Notes that link to the current one are listed after it, collapsed, each with the line of context around the mention; the Links panel still carries the full list.
- **The reading canvas is editorial now**: a warm paper background with charcoal ink and one cobalt accent, 17px body text on a 65–80 character measure, callouts as tinted surfaces with a colored left edge instead of full colored boxes, tables ruled horizontally with a firmer line under the header, and consistent 8px-scale radii.
- **The read-only badge explains itself.** Clicking it says why the app cannot edit — by design, not by permission — and offers the next action: view raw source, open in the default editor, or reveal in Files.
- **Pinned & recent sits above the file tree.** Note menu → Pin/Unpin Note keeps a note at the top of the Files page; the five most recent notes follow. Selected sidebar rows now carry a left accent marker, not contrast alone.

## 1.2.0 — 2026-09-01

The GUI-first release: nothing about installing or using the reader requires a terminal beyond one paste.

- **The one-time sandbox step is now a window.** Launched from the applications grid on a stock Ubuntu, the reader used to die silently to stderr; it now opens a plain-GTK setup window (no WebKit needed — that is the part that cannot start) explaining the situation, offering a single copy-paste command, and relaunching the reader itself when "check again" finds the profile installed. The terminal flow still works headless, unchanged.
- **The documentation lives inside the app.** `F1` opens the user guide, the menu carries Getting Started beside it, and the welcome page links both — rendered through the reader's own pipeline, so a fresh install can read its manual before opening any vault. The docs ship with the package.
- The README and getting-started guide now lead with the desktop flow — app grid, welcome page, Open With from the file manager — with the CLI as the alternative. (Markdown files and folders were already registered for Open With; that part just needed saying.)

## 1.1.1 — 2026-09-01

- **The mind map now has an obvious way back.** The map page carries a "Back to <note>" link, `Ctrl+M` toggles — note to map, map back to note — and the map keeps counting as its note, so the window title, tree selection, and the toggle itself all keep working while it is shown. (Back always worked; nothing said so.)

## 1.1.0 — 2026-09-01

- **Folders can be hidden.** Right-click a folder in the tree to hide it — it leaves the tree, quick-open, and search results (link panels, graph, and Dataview stay complete, since those answer explicit questions). The toast offers Unhide, and View → Unhide All Folders clears the reader's list. Obsidian's own excluded-files setting (`userIgnoreFilters` in `.obsidian/app.json`) is honored read-only on top, and stays in force when the reader's list is cleared. The reader's list lives in its own config, never in the vault.
- **Any note can be viewed as a mind map** (`Ctrl+M`, or Note menu → View as Mind Map): headings and nested bullets become a right-growing tree of rounded nodes with per-depth colors, heading nodes link to their place in the note, and Back returns to the rendered page. Static SVG, no JavaScript, labels cleaned of markup and escaped.

## 1.0.0 — 2026-09-01

The completion release: the reader now renders every content type the vault it was built against actually contains.

- **Kanban boards render as boards.** A note with `kanban-plugin` frontmatter shows its `##` headings as columns and its task items as cards: wikilinks inside cards resolve, done cards dim, the `***` archive becomes its own lane, and boards scroll horizontally (and wrap in print). Verified against every board in a large real vault.
- **Excalidraw drawings render as static SVG** — rectangles, ellipses, diamonds, arrows, lines, freehand strokes, and text, at their drawn positions and rotations. The LZ-String compression Excalidraw uses is decoded by a pure-Python port (decode-only); the JSON is treated as hostile input like canvas.
- **Vault CSS snippets apply.** The snippets `.obsidian/appearance.json` enables load through a strict allowlist sanitizer — plain rules and @media blocks survive; any declaration that could touch the network or smuggle an escape (`url()`, `@import`, `expression()`, a backslash) is dropped whole. Pages carry Obsidian's `markdown-preview-view` class and the note's own `cssclasses`, so class-scoped snippets match. A View-menu toggle turns them off.
- Accessibility: the local-graph pane carries an accessible label; tree rows already announce their note names.
- The Flatpak manifest's dependency list is current. Building it still needs `flatpak-builder`, which is not installed here — the build remains unverified and says so.

## 0.9.0 — 2026-09-01

Dataview, in pure Python — no JavaScript, same as everything else.

- **DQL queries evaluate.** `TABLE` (with `WITHOUT ID` and aliases), `LIST`, and `TASK` blocks run against the live index: `FROM` folder/tag/`[[]]` sources with `and`/`or`/negation, chained `WHERE`/`SORT`/`GROUP BY`/`FLATTEN`/`LIMIT` in written order, `this.` context, bracket access for spaced field names, lambdas in `filter`/`map`, date and duration arithmetic, and a 30-function standard library (`choice`, `default`, `dateformat` with Luxon tokens, `dur`, `contains`, `length`, and friends). Results are live: the vault monitor already re-renders what changes.
- **Inline expressions evaluate** — the `= this.field` spans templates lean on render their values in place.
- **`.base` files render**: table views with filters (`and`/`or`/`not` over the Bases expression dialect — `file.hasTag`, `file.inFolder`, `file.hasProperty`, comparisons, `today()` date math), column order, sort, and displayName mapping. Plugin view types (TaskNotes and similar) are named as not rendered, never faked.
- **Anything outside the surface degrades honestly**: the block renders as labeled source with the parser's reason, and `dataviewjs` stays inert by design.
- **Acceptance against a large real vault**: 99% of Dataview blocks evaluate (the few failures are deliberately broken examples) at 58 ms average, as do more than 99% of inline expressions, and every `.base` file is row-for-row correct against grep ground truth.
- Fixed en route, and it matters beyond Dataview: PyYAML reads YAML 1.1, where a bare `Yes` is a boolean — Obsidian keeps it a string, so `Outage: Yes` never matched `== "Yes"`. The frontmatter loader now resolves only `true`/`false` as booleans, matching Obsidian.
- The index schema bumped (cached scans now carry frontmatter and tasks), so the first launch after upgrading rebuilds the cache: cold ~21 s on a large real vault, warm ~2 s after.

## 0.8.1 — 2026-09-01

- **Fixed PDF export splitting and clipping content.** The stylesheet had no print rules, so paper got the screen layout: code and tables kept their scroll containers (which clip on paper — long lines simply vanished off the right edge), and boxes could be sliced across page boundaries. A print stylesheet now makes wide code and tables wrap instead of clip, keeps code blocks, callouts, tables rows, images, math, and the properties panel whole across page breaks, keeps headings attached to what follows them, repeats table headers on each page, forces the light palette (backgrounds are not printed, so a dark-theme export was pale-gray text on white paper), hides media players, and prints only the open state of foldable sections.
- The GUI smoke now proves export quality in both directions, not just that a PDF exists: the tail of an overflowing code line must survive into the extracted text, the ink of a known word must be dark even when exporting from the dark theme, and an eight-block document must reach page two with no block straddling a page boundary — each check shown to fail against the unfixed stylesheet.

## 0.8.0 — 2026-09-01

- **Embedded PDF preview.** Opening a PDF from the file tree (or a PDF embed's link) now shows it in an in-app viewer: pages rendered on demand through the system's own Poppler library, fit-to-width with zoom, an Open Externally escape hatch, and a page cap plus a small surface cache bounding memory. Requires the optional `gir1.2-poppler-0.18` package; without it, PDFs open externally exactly as before — the viewer is never half-present.

## 0.7.0 — 2026-09-01

The fidelity layer: more of what a vault actually contains renders as itself.

- **Math.** `$...$` and `$$...$$` TeX renders as native MathML (via latex2mathml — pure Python, no JavaScript), with block math centered and inline math in the text flow. Currency stays prose: an opener must touch its content and a closer may not be followed by a digit, so "$5 and $10" never becomes a formula. TeX the converter refuses — or anything over the size bound — falls back to the labeled source.
- **Canvas files render.** A `.canvas` opens in the reading pane as a static page: text cards, file cards (linked to their notes), groups, colors, and SVG arrows with labels, laid out at the canvas's own coordinates. Verified against every canvas in a large real vault. The JSON is treated as hostile: coordinates are numerically coerced per node, colors pass a palette-or-hex check, every string is escaped, and node/size bounds cap the work.
- **Typography controls.** Menu → Typography: font (theme default, serif, sans, mono), line width (narrow to full), and line spacing (compact to relaxed) — persisted, applied to every page including previews and canvases.
- Deferred, named: embedded PDF preview needs `gir1.2-poppler-0.18`, which is not installed here — code that cannot be run even once does not ship. External open remains. Heading folding stays out for a structural reason: without JavaScript, a `#anchor` cannot open the closed `<details>` it lands in, so folding would break outline navigation.

## 0.6.0 — 2026-09-01

The retrieval layer: finding a note now works the way the best launchers do.

- **Fuzzy quick-open.** The as-you-type filename search matches subsequences with scoring — word-boundary hits, consecutive runs, and filename matches rank higher — so `scnt` finds "Second Note" and `pmn` finds "Personal/Meeting Notes". An empty query shows your recent notes.
- **Recent notes** are remembered across sessions (the twenty most recently opened).
- **Search hits open highlighted**: activating a full-text result highlights every match of the leading term in the opened note and scrolls to the first one.
- **A local graph pane** — a sixth sidebar page drawing the current note and its neighbors natively (no JavaScript): bidirectional links in accent color, backlinks solid, outgoing dimmed. Click a node to open it. Capped at thirty neighbors so hub notes stay legible.
- **Fixed a crash that could kill the app at any moment after 0.5**: Python's garbage collector can run on the index-sync thread, and cyclic garbage there can hold GTK and WebKit objects (a closed tab's web view) whose finalizers abort off the main thread — silently, with no message. Automatic collection is now off and the main loop collects on a timer, so GObjects are only ever finalized where they were born. Found because the GUI smoke started dying with exit 134 *after* printing an all-green PASS.

## 0.5.0 — 2026-09-01

The live layer: the reader now tracks the vault while it is open, and remembers it between launches.

- **A persistent index** in `~/.cache/obsidian-reader/`, one SQLite file per vault: note scans plus an FTS5 full-text index. A launch reads only what changed since last time: on a large real vault, a warm start indexes in ~1.2 s instead of ~8.5 s, and the first-ever build is ~9 s. The cache is derived data: corruption or a schema change wipes and rebuilds it silently, and "Clear Index Cache" in the menu does the same on demand. Expect it to cost disk roughly proportional to the vault's text (about half its size).
- **The vault is watched.** Every non-hidden directory carries a file monitor; changes are debounced for two seconds, then a background sync re-reads only the changed notes, re-resolves every link, and refreshes the tree, panels, and search — so a note written by another app (or synced in from another device) is searchable and backlinked without touching Reload. A rename or deletion re-resolves links vault-wide, so a link that was "missing" resolves the moment its target appears.
- **Full-text search is now ranked** by FTS5's BM25 relevance instead of index order, with token-prefix matching (`ship` finds "Ships") and match snippets from the index itself. Queries run in ~65 ms against a large real vault. Query text is quoted into plain prefix terms, so FTS query syntax can never be injected.
- The `path:`, `file:`, and `tag:` operators, the graph, and every panel work exactly as before — the graph now assembles from cached scans in about a second.
- Fixed en route: the first cold build took 131 s because deleting an FTS row by its unindexed `rel` column is a full-table scan — O(n²) across a build. Deletion now goes through a stored rowid; 131 s → 8.8 s.

## 0.4.0 — 2026-09-01

- A vault-wide link graph, built in the background alongside the search index in one pass over the notes. It powers three new sidebar pages beside Files and Search:
  - **Links** — every note that links to the current one ("linked mentions"), each with the line of context around the mention, plus the note's outgoing links with unresolved and ambiguous targets named as such. Links inside fenced code, inline code, and comments do not count; media embeds stay out of the graph.
  - **Tags** — every tag in the vault (inline and frontmatter), with counts and a filter box. Activating a tag runs a `tag:` search.
  - **Bookmarks** — the vault's own `.obsidian/bookmarks.json`, read-only, groups flattened into headers; entries pointing at files that no longer exist are dropped.
- Search operators: `path:`, `file:`, and `tag:` narrow a full-text search (`tag:` matches nested children, so `tag:project` finds `project/tag`). A query of filters alone works too.
- Hover previews: rest the pointer on a wikilink for a moment and a popover shows the opening of the target note, rendered through the same sanitized pipeline with its own tight embed budget. The preview surface takes no input, so a click always lands on the page under it.
- The mention list per note and the bookmark count are bounded (`READER_MAX_MENTIONS_PER_TARGET`, `READER_MAX_BOOKMARKS`), so hostile input cannot grow either without limit.
- The GUI smoke run now refuses to pass when zero checks ran: it previously forwarded its activation to an already-running reader instance and reported an empty failure list as a pass. It runs non-unique now, and an empty run is a failure.

## 0.3.0 — 2026-09-01

- Tabs: `Ctrl+T` opens a new tab, `Ctrl+W` closes one (the last tab shows the welcome page instead of closing the window), and middle-click or `Ctrl+click` on a file-tree note or an in-note wikilink opens it in a new tab. A plain click still opens in the current tab. Every tab has its own history and outline; open tabs are restored with the session. All tabs share one WebKit context, so the process cost of a tab is a web view, not a browser.
- The sidebar is now resizable by dragging the divider, and its width persists across sessions. Deep folder trees no longer squeeze the note names into ellipses.
- A single click on a folder now expands or collapses it; notes likewise open on single click.

## 0.2.2 — 2026-09-01

- The AppArmor profile from 0.2.1 loaded but never attached, so the app still refused to start: AppArmor attaches a profile by interpreter path, and launching through the venv console script's `#!` shebang bypasses that (proven by direct test — the same interpreter attaches when exec'd directly or via its symlink, and not via a shebang). The launcher now execs the venv interpreter directly, which attaches the profile and starts WebKit's sandbox correctly.
- When the sandbox probe fails but the profile is already installed and unattached, the preflight now explains the shebang trap and points at the launcher, instead of telling you to install the profile you already have.

## 0.2.1 — 2026-09-01

- On stock Ubuntu 24.04+ the app could not start from a normal terminal: the kernel's unprivileged-user-namespace restriction blocks WebKit's bubblewrap sandbox (`bwrap: setting up uid map: Permission denied`). The launcher now preflights this before WebKit crashes and prints the fix — a rendered AppArmor profile granting `userns` to this app's interpreter alone, kept narrow by `make install` giving the venv a private interpreter copy. `SOLANDER_SKIP_SANDBOX_CHECK=1` bypasses the check.
- The sandbox stays on: WebKitGTK 2.52 ignores the old sandbox-disable variables, so the profile is the supported path, and it is the same mechanism Ubuntu ships for browsers.

## 0.2.0 — 2026-09-01

- Reading (zen) mode: `F11` hides the sidebar, header, and window chrome, leaving only the note; `Esc` or `F11` leaves, restoring the sidebar to how it was.
- PDF export: `Ctrl+Shift+E` (or the menu) prints the current rendered note to a user-chosen file through WebKit's print pipeline. A target inside the vault is refused — the zero-write promise covers exports too.
- The GUI smoke run now proves both on a live display, including the `%PDF` magic bytes of an actual export, and runs against isolated application state so a restored session cannot race it.

## 0.1.0 — 2026-09-01

First release. A read-only GTK4/libadwaita reader for Obsidian vaults.

- Opens a folder as a vault or a single note, in place, from the CLI, the file dialogs, drag-and-drop, or a recent-vaults list; a second launch hands its path to the running instance.
- Renders CommonMark and GFM plus the Obsidian layer: wikilinks with aliases, heading and block links, note/section/block embeds with cycle detection and a depth limit, callouts (foldable and nested), highlights, hidden comments (`%%` and HTML), inline tags, extended task states, footnotes (inline included), frontmatter as a collapsible Properties panel, image sizing syntax, and syntax-highlighted code.
- Resolves links path-first then by filename; ambiguous names open a chooser, never an arbitrary note; missing links are visibly marked.
- Vault-wide filename and full-text search with snippets, in-note find, back/forward history, outline navigation, light/dark/system appearance, zoom, session restore, and a read-only indicator.
- Security: JavaScript disabled in the rendering surface (the app refuses to start if it cannot be), raw note HTML escaped, generated HTML passed through an allowlist sanitizer, assets served only through a vault-contained URI scheme, remote resources blocked, `http`/`https` links handed to the system browser, every other scheme refused. Dataview/Templater/mermaid blocks render as labeled inert source.
- Resource bounds proven against real attack payloads: YAML aliases in frontmatter are refused (a 352-byte alias bomb froze property rendering before the fix), and a per-page embed budget caps multiplicative embed fan-out (six small notes rendered a 23 MB page in 29 s before the fix; 0.2 s after).
- Zero-write guarantee covered by a test that hashes a vault before and after a full index-and-render pass; the full suite is 77 tests plus a scripted GUI smoke run. CI (ruff, pytest on 3.12/3.13, semgrep) and `SECURITY.md` ship with the repo.
