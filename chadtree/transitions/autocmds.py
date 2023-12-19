from asyncio import Task, create_task, sleep
from itertools import chain
from typing import Optional

from pynvim_pp.buffer import Buffer
from pynvim_pp.nvim import Nvim
from pynvim_pp.rpc_types import NvimError
from pynvim_pp.window import Window
from std2.asyncio import cancel
from std2.cell import RefCell

from ..consts import URI_SCHEME
from ..fs.ops import ancestors, is_file
from ..lsp.diagnostics import poll
from ..nvim.markers import markers
from ..registry import NAMESPACE, autocmd, rpc
from ..state.next import forward
from ..state.ops import dump_session
from ..state.types import State
from .shared.current import new_current_file, new_root
from .shared.wm import find_current_buffer_path, is_chadtree_buf_name
from .types import Stage

_CELL = RefCell[Optional[Task]](None)


@rpc(blocking=False)
async def _when_idle(state: State) -> None:
    if task := _CELL.val:
        _CELL.val = None
        await cancel(task)

    async def cont() -> None:
        await sleep(state.settings.idle_timeout)
        diagnostics = await poll(state.settings.min_diagnostics_severity)
        await forward(state, diagnostics=diagnostics)

    _CELL.val = create_task(cont())


_ = autocmd("CursorHold", "CursorHoldI") << f"lua {NAMESPACE}.{_when_idle.method}()"


@rpc(blocking=False)
async def save_session(state: State) -> Stage:
    """
    Save CHADTree state
    """

    await dump_session(state)
    new_state = await forward(state, vim_focus=False)
    return Stage(new_state)


_ = autocmd("FocusLost", "ExitPre") << f"lua {NAMESPACE}.{save_session.method}()"


@rpc(blocking=False)
async def _focus_gained(state: State) -> Stage:
    """ """

    new_state = await forward(state, vim_focus=True)
    return Stage(new_state)


_ = autocmd("FocusGained") << f"lua {NAMESPACE}.{_focus_gained.method}()"


@rpc(blocking=False)
async def _record_win_pos(state: State) -> Stage:
    """
    Record last windows
    """

    win = await Window.get_current()
    win_id = win.data

    window_order = {
        wid: None
        for wid in chain(
            (wid for wid in state.window_order if wid != win_id), (win_id,)
        )
    }
    new_state = await forward(state, window_order=window_order)
    return Stage(new_state)


_ = autocmd("WinEnter") << f"lua {NAMESPACE}.{_record_win_pos.method}()"


@rpc(blocking=False)
async def _changedir(state: State) -> Stage:
    """
    Follow cwd update
    """

    cwd = await Nvim.getcwd()
    new_state = await new_root(state, new_cwd=cwd, indices=frozenset())
    return Stage(new_state)


_ = autocmd("DirChanged") << f"lua {NAMESPACE}.{_changedir.method}()"


@rpc(blocking=False)
async def _update_follow(state: State) -> Optional[Stage]:
    """
    Follow buffer
    """

    win = await Window.get_current()
    if await win.vars.get(bool, URI_SCHEME):
        buf = await Buffer.get_current()
        name = await buf.get_name()
        if name and not is_chadtree_buf_name(name):
            await win.vars.set(URI_SCHEME, False)
            for key, val in state.settings.win_actual_opts.items():
                await win.opts.set(key, val=val)

    else:
        name = None

    try:
        if (current := await find_current_buffer_path(name)) and await is_file(current):
            if state.vc.ignored & {current, *ancestors(current)}:
                return None
            else:
                stage = await new_current_file(state, current=current)
                return stage
        else:
            return None
    except NvimError:
        return None


_ = autocmd("BufEnter") << f"lua {NAMESPACE}.{_update_follow.method}()"


@rpc(blocking=False)
async def _update_markers(state: State) -> Stage:
    """
    Update markers
    """

    mks = await markers()
    new_state = await forward(state, markers=mks)
    return Stage(new_state)


_ = autocmd("QuickfixCmdPost") << f"lua {NAMESPACE}.{_update_markers.method}()"
