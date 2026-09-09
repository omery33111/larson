import { useState } from 'react'
import Checkbox from '@mui/material/Checkbox'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import { FiBriefcase, FiChevronDown } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  getOverviewAsync, selectAllAccounts, selectAvailableAccounts,
  selectOverview, selectSelectedAccounts, toggleAccount
} from './analyticsSlice'
import { money } from './format'
import './analytics.css'



/**
 * Picks which accounts the whole page is computed over.
 *
 * A funded account and a personal one are two different traders; averaging them describes
 * neither. Ticking several at once answers the question the other way round - "what do these
 * look like together?" - which is exactly what a prop trader running several accounts wants.
 *
 * Changing the selection re-fetches the overview. That costs one local request and no model
 * call: the statistics are recomputed from the trades table anyway, so a filter is just a
 * shorter list going in.
 */
const AccountSelector = () => {

  const dispatch = useAppDispatch();

  const accounts = useAppSelector(selectAvailableAccounts);
  const selected = useAppSelector(selectSelectedAccounts);
  const currency = useAppSelector(selectOverview).currency || 'USD';

  // Purely positional state for the popup, which is why it stays local rather than in the
  // slice - it is an anchor element, not application state.
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  // Nothing to choose between when there is only one account.
  if (accounts.length < 2) return null;

  const isAll = selected === null;
  const activeIds = isAll ? accounts.map((a) => a.account_id) : selected;

  // Redux applies a reducer synchronously, so the thunk that follows already reads the new
  // selection through getState. No waiting, no effect watching the value change.
  const onToggle = (accountId: string) => {
    dispatch(toggleAccount(accountId));
    dispatch(getOverviewAsync());
  };

  const onSelectAll = () => {
    dispatch(selectAllAccounts());
    dispatch(getOverviewAsync());
  };

  const label = isAll
    ? `כל החשבונות (${accounts.length})`
    : activeIds.length === 1
      ? accounts.find((a) => a.account_id === activeIds[0])?.label || activeIds[0]
      : `${activeIds.length} חשבונות נבחרו`;

  return (
    <div className="account-selector">

      <button className="account-trigger" onClick={(e) => setAnchor(e.currentTarget)}>
        <span className="account-trigger-icon"><FiBriefcase /></span>
        <span className="account-trigger-label">{label}</span>
        <span className="account-trigger-arrow"><FiChevronDown /></span>
      </button>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        /* MUI locks body scroll while a menu is open, which removes the page scrollbar and
           shifts everything sideways by its width. The page underneath is not going
           anywhere, so the lock is simply not wanted here. */
        disableScrollLock
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        transformOrigin={{ vertical: 'top', horizontal: 'center' }}
        slotProps={{
          paper: {
            sx: {
              minWidth: 280,
              backgroundColor: '#15181f',
              border: '1px solid #2b303b',
              borderRadius: '10px',
              color: '#e8e8e8',
              marginTop: '6px',
            },
          },
        }}
      >
        <MenuItem onClick={onSelectAll} className="account-option">
          <Checkbox
            checked={isAll}
            sx={{ color: '#3a4150', '&.Mui-checked': { color: '#f0b90b' }, padding: '4px' }}
          />
          <span className="account-option-label">הצגת כל החשבונות</span>
        </MenuItem>

        <div className="account-divider" />

        {accounts.map((account) => (
          <MenuItem
            key={account.account_id}
            onClick={() => onToggle(account.account_id)}
            className="account-option"
          >
            <Checkbox
              checked={activeIds.includes(account.account_id)}
              sx={{ color: '#3a4150', '&.Mui-checked': { color: '#f0b90b' }, padding: '4px' }}
            />
            <span className="account-option-body">
              <span className="account-option-label">{account.label}</span>
              <span className="account-option-meta">
                {account.trades} עסקאות ·{' '}
                <span className={account.net_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                  {money(account.net_pnl, currency)}
                </span>
              </span>
            </span>
          </MenuItem>
        ))}
      </Menu>

    </div>
  )
}

export default AccountSelector
