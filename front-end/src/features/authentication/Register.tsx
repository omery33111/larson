import { useState } from 'react';
import { AiOutlineUser } from 'react-icons/ai';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { useAppDispatch } from "../../app/hooks";
import { registerAsync, reset } from "./authenticationSlice";
import './authentication.css';



const Register = () => {
    const [formData, setFormData] = useState
    ({
        username: "",
        password: "",
        password2: "",
        email: ""
    })
    const { username, password, password2, email } = formData


    const navigate = useNavigate()
    const dispatch = useAppDispatch()



    const onChange = (event: any) => {setFormData((PreviousState) => ({ ...PreviousState, [event.target.name]: event.target.value}))}

    const onSubmit = (event: any) => {
      event.preventDefault();

      const passwordRegex = /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}$/;

      if (!passwordRegex.test(password)) {
        toast.error("סיסמה צריכה להכיל לפחות 8 תוים, אות גדולה, אות קטנה, ומספר");
      } else if (password !== password2) {
        toast.error("הסיסמאות לא זהות");
      } else {
        const userData = {
          username,
          email,
          password
        };

        dispatch(registerAsync(userData))
          .then((action) => {
            if (action.meta.requestStatus === "fulfilled") {
              // "isSuccess" is shared with the login flow, so it is cleared before leaving
              dispatch(reset())
              navigate("/authentication/login")
            }
          })
          .catch((error) => {
            toast.error(error.message);
          });
      }
    }

    return (
        <div className="app-container auth-page">

          <form className="auth-form" onSubmit={onSubmit}>

            <h1 className="auth-title">
              <AiOutlineUser /> הרשמה
            </h1>

            <div className="auth-field">
              <input
                type="text"
                className="app-input"
                id="username"
                name="username"
                value={username}
                placeholder="הזן שם משתמש"
                onChange={onChange}
              />
            </div>

            <div className="auth-field">
              <input
                type="password"
                className="app-input"
                id="password"
                name="password"
                value={password}
                placeholder="סיסמה"
                onChange={onChange}
              />
            </div>

            <div className="auth-field">
              <input
                type="password"
                className="app-input"
                id="password2"
                name="password2"
                value={password2}
                placeholder="וידוא סיסמה"
                onChange={onChange}
              />
            </div>

            <div className="auth-field">
              <input
                type="text"
                className="app-input"
                id="email"
                name="email"
                value={email}
                placeholder="כתובת אימייל"
                onChange={onChange}
              />
            </div>

            <div className="auth-actions">
              <button type="submit" className="app-btn app-btn-primary">
                הירשמות
              </button>

              <button type="button" className="app-btn app-btn-dark auth-secondary-btn" onClick = {() => navigate('/authentication/login')}>
                כבר יש לי חשבון
              </button>
            </div>

          </form>

        </div>
      )
}



export default Register
