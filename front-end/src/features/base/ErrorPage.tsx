import { useNavigate } from 'react-router-dom'
import './base.css';



const ErrorPage = () => {

  const navigate = useNavigate();

  return (
    <div className="app-container home-page">

      <h1 className="home-title">404</h1>

      <p className="home-subtitle">הדף שחיפשת לא קיים.</p>

      <button className="app-btn app-btn-dark" onClick = {() => navigate('/')}>
        חזרה לדף הבית
      </button>

    </div>
  )
}

export default ErrorPage
