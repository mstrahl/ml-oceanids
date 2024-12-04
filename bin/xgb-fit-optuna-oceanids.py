import os,optuna,time,warnings,joblib
import sklearn.metrics
from sklearn.metrics import mean_squared_error
import pandas as pd
import xgboost as xgb
import numpy as np
import importlib,sys
# give the name of the module as cmd argument
warnings.filterwarnings("ignore")
### XGBoost with Optuna hyperparameter tuning for OCEANIDS
# note: does not save trained mdl
startTime=time.time()

# import harbor module
if len(sys.argv) != 2:
    print("Usage: python script.py <module_name>")
    sys.exit(1)    
module_name = sys.argv[1]    
print(module_name)
try:
    module = importlib.import_module(module_name)
    print(f"Successfully imported {module_name}")
    globals().update({k: getattr(module, k) for k in dir(module) if not k.startswith("__")})
except ImportError:
    print(f"Failed to import {module_name}")

data_dir='/home/ubuntu/data/ML/training-data/OCEANIDS/' # training data
mod_dir='/home/ubuntu/data/ML/models/OCEANIDS/' # saved mdl
res_dir='/home/ubuntu/data/ML/results/OCEANIDS/'
optuna_dir='/home/ubuntu/data/ML/' # optuna storage

# move to correct dir for optuna study 
os.chdir(optuna_dir)
print(os.getcwd())

### optuna objective & xgboost
def objective(trial):
    # hyperparameters
    param = {
        "objective":"reg:quantileerror",#"reg:squarederror",
        "num_parallel_tree":1,#trial.suggest_int("number_parallel_tree", 1, 10),
        "max_depth":trial.suggest_int("max_depth",3,18),
        "subsample":trial.suggest_float("subsample",0.01,1),
        "learning_rate":trial.suggest_float("learning_rate",0.01,0.7),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.01, 1.0),
        "n_estimators":trial.suggest_int("n_estimators",50,1000),
        "min_child_weight":1,
        "quantile_alpha":0.95,
        "alpha":trial.suggest_float("alpha", 0.000000001, 1.0),
        "n_jobs":64,
        "random_state":99,
        "early_stopping_rounds":50,
        "eval_metric":"mae"#rmse"
    }
    eval_set=[(valid_x,valid_y)]

    xgbr=xgb.XGBRegressor(**param)
    bst = xgbr.fit(train_x,train_y,eval_set=eval_set)
    preds = bst.predict(valid_x)
    accuracy = np.sqrt(mean_squared_error(valid_y,preds))
    print("RMSE: "+str(accuracy))
    
    # Save model if it's the best so far
    if not hasattr(objective, 'best_rmse'):  # Initialize best_rmse if it doesn't exist
        objective.best_rmse = float('inf')
    if accuracy < objective.best_rmse:
        objective.best_rmse = accuracy
        joblib.dump(xgbr, mod_dir+mdl_name+"best_optuna.txt")  # Save model to file
        print("New best model saved with RMSE:", accuracy)

    return accuracy


### Read in training data, split to preds and vars
print(fname)
df=pd.read_csv(data_dir+fname,usecols=cols_own)
#df=pd.read_csv(data_dir+fname)


# drop NaN values
df=df.dropna(axis=1, how='all')
s1=df.shape[0]
df=df.dropna(axis=0,how='any')
s2=df.shape[0]
print('From '+str(s1)+' rows dropped '+str(s1-s2)+', apprx. '+str(round(100-s2/s1*100,1))+' %')
df['utctime']= pd.to_datetime(df['utctime'])
headers=list(df) # list column headers
#print(df)

# Split to train and test by years, KFold for best split (k=5)
print('test ',test_y,' train ',train_y)
train_stations,test_stations=pd.DataFrame(),pd.DataFrame()
for y in train_y:
        train_stations=pd.concat([train_stations,df[df['utctime'].dt.year == y]],ignore_index=True)
for y in test_y:
        test_stations=pd.concat([test_stations,df[df['utctime'].dt.year == y]],ignore_index=True)

# Split to predictors (preds) and predictand (var) data
var_headers=list(df[[pred]])
preds_headers=list(df[headers].drop(['utctime',pred], axis=1))
train_x=train_stations[preds_headers] 
valid_x=test_stations[preds_headers]
train_y=train_stations[var_headers]
valid_y=test_stations[var_headers]
    
### Optuna trials
study = optuna.create_study(storage="sqlite:///MLexperiments.sqlite3",study_name=xgbstudy,direction="minimize",load_if_exists=True)
study.optimize(objective, n_trials=100, timeout=432000)

print("Number of finished trials: ", len(study.trials))
print("Best trial:")
trial = study.best_trial

print("  Value: {}".format(trial.value))
print("  Params: ")
for key, value in trial.params.items():
    print("    {}: {}".format(key, value))

executionTime=(time.time()-startTime)
print('Execution time in minutes: %.2f'%(executionTime/60))